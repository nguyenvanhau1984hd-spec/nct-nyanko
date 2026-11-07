import discord
import os
from bcsfe import core
from bcsfe.core.server.server_handler import ServerHandler

core.core_data.init_data()
GAME_VERSION_TEXT = os.getenv("BCSFE_GAME_VERSION", "15.6.0")
LAST_NEKO_CHEATER_REMOVALS = {}
LAST_BULK_FAILURES = {}

def _get_recovery(user_id: int):
    return _load_recovery().get(str(user_id))

# 사용자가 선택한 항목 -> 실제 SaveFile 속성
# BCSFE SaveFile에서 직접 확인되는 기본 수치들만 연결.
SCALAR_FIELDS = {
    "통조림": "catfood",
    "XP": "xp",
    "NP": "np",
    "리더십/통솔력": "leadership",
    "냥코 티켓": "normal_tickets",
    "레어 티켓": "rare_tickets",
    "플래티넘 티켓": "platinum_tickets",
    "플래티넘 조각": "platinum_shards",
    "레전드 티켓": "legend_tickets",
}

CATEGORIES = {
    "아이템": [
        "통조림", "XP", "NP", "리더십/통솔력",
        "냥코 티켓", "레어 티켓", "플래티넘 티켓",
        "플래티넘 조각", "럭키 티켓", "레전드 티켓",
        "럭키 티켓G",
    ],
    "모든 캐릭터": [
        "전체 해금", "전체 만렙", "전체 진화",
        "전체 해금 + 만렙 + 진화",
        "전체 본능 해방", "전체 본능 MAX", "전체 특정 본능 MAX",
        "전체 3진화", "전체 4진화",
        "전체 레벨 설정", "전체 기본레벨 MAX", "전체 플러스레벨 MAX",
    ],
    "캐릭터 가격·쿨타임": [
        "캐릭터 가격 수정", "소환 쿨타임 수정",
    ],
    "특정 캐릭터": [
        "캐릭터 ID로 확인",
        "캐릭터 이름으로 찾기",
    ],
    "스토리·보물": [
        "세계편", "미래편", "우주편",
        "레전드 스토리", "보물 최고급", "전체 클리어",
    ],
    "기타 아이템": [
        "스피드 업", "트레저 레이더", "고양이 도령",
        "야옹컴", "고양이 박사", "스냥이퍼",
        "고양이 드링크A", "고양이 드링크B", "고양이 드링크C",
        "캣츠아이 EX", "캣츠아이 레어",
        "캣츠아이 슈퍼 레어", "캣츠아이 울트라 슈퍼 레어",
        "캣츠아이 레전드", "캣츠아이 다크",
    ],
    "개다래 열매": [
        "초록 개다래", "보라 개다래", "빨강 개다래",
        "파랑 개다래", "노랑 개다래", "무지개 개다래",
        "고대 개다래", "악마 개다래", "황금 개다래",
    ],
    "개다래 씨앗": [
        "초록 씨앗", "보라 씨앗", "빨강 씨앗",
        "파랑 씨앗", "노랑 씨앗", "무지개 씨앗",
        "고대 씨앗", "악마 씨앗", "황금 씨앗",
    ],
    "수석": [
        "자수석", "홍수석", "청수석",
        "녹수석", "황수석", "무지개 수석",
    ],
    "수석 결정": [
        "자수석 결정", "홍수석 결정", "청수석 결정",
        "녹수석 결정", "황수석 결정",
    ],
    "가마토토": [
        "가마토토 만렙", "조수 슬롯/조수 편집",
        "탐험 시간", "보상 설정",
    ],
    "계정": [
        "골드패스", "계정 편의 설정",
    ],
}

# =========================
# BCSFE 작업
# =========================

def load_save_sync(
    transfer_code: str,
    confirmation_code: str,
    country_code: str = "kr",
) -> ServerHandler:
    """
    실제 BCSFE ServerHandler.from_codes()를 사용해
    Battle Cats 서버에서 사용자가 제공한 세이브를 다운로드한다.
    """
    cc = core.CountryCode.from_code(country_code.strip().lower() or "kr")
    gv_text = GAME_VERSION_TEXT
    parts = gv_text.split(".")
    if len(parts) != 3 or not all(x.isdigit() for x in parts):
        raise ValueError("BCSFE_GAME_VERSION은 예: 15.5.0 형식이어야 합니다.")
    gv = core.GameVersion(int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2]))

    handler, result = ServerHandler.from_codes(
        transfer_code.strip(),
        confirmation_code.strip(),
        cc,
        gv,
        print=False,
        save_backup=False,
    )

    if handler is None:
        detail = ""
        if result is not None and result.response is not None:
            detail = f" (HTTP {result.response.status_code})"
        raise RuntimeError(
            "세이브 다운로드에 실패했습니다." + detail +
            "\n이어하기 코드/인증 번호와 게임 버전을 확인하세요."
        )

    return handler


def set_scalar_sync(handler: ServerHandler, item_name: str, value: int) -> None:
    save = handler.save_file
    field = SCALAR_FIELDS.get(item_name)

    if field is None:
        raise ValueError(
            f"현재 버전에서 직접 연결된 항목이 아닙니다: {item_name}"
        )

    if not hasattr(save, field):
        raise ValueError(
            f"BCSFE SaveFile에 '{field}' 필드가 없습니다."
        )

    setattr(save, field, value)



def upload_sync(handler: ServerHandler) -> tuple[str, str]:
    """
    수정된 SaveFile을 BCSFE의 공식 업로드 흐름으로 업로드하고
    새 transfer/confirmation code를 받는다.
    """
    codes = handler.get_codes(upload_managed_items=True)
    if codes is None:
        raise RuntimeError("세이브 업로드 또는 새 코드 발급에 실패했습니다.")

    return codes



# =========================
# 디스코드 UI
# =========================

def _as_display_value(value):
    """Return a scalar account value suitable for Discord output, or None."""
    if value is None or callable(value):
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, str):
        return value.strip() or None
    try:
        wrapped = getattr(value, "value", None)
        if isinstance(wrapped, (int, float, str)) and not callable(wrapped):
            return _as_display_value(wrapped)
    except Exception:
        pass
    return None


def _find_save_scalar(save, aliases, fuzzy_tokens=()):
    """Find account stats across known BCSFE field names and common containers.

    The BCSFE data model has changed field names between versions; this helper
    searches a small, bounded set of containers and returns only scalar values.
    """
    normalise = lambda value: re.sub(r"[^a-z0-9]", "", str(value).casefold())
    wanted = {normalise(alias) for alias in aliases}
    owners = [save]
    for container_name in (
        "account", "account_data", "player", "player_data", "stats",
        "resources", "user", "game_data", "misc", "cat_base",
    ):
        try:
            child = getattr(save, container_name, None)
        except Exception:
            child = None
        if child is not None and not callable(child) and not isinstance(child, (str, bytes, int, float, bool, list, tuple, dict, set)):
            owners.append(child)

    seen = set()
    for owner in owners:
        if id(owner) in seen:
            continue
        seen.add(id(owner))
        try:
            names = dir(owner)
        except Exception:
            names = []
        # Exact aliases first, so generic fuzzy matches don't select unrelated fields.
        for attr in names:
            if attr.startswith("_") or normalise(attr) not in wanted:
                continue
            try:
                displayed = _as_display_value(getattr(owner, attr))
            except Exception:
                displayed = None
            if displayed is not None:
                return displayed
        if fuzzy_tokens:
            for attr in names:
                if attr.startswith("_"):
                    continue
                norm = normalise(attr)
                if not any(token in norm for token in fuzzy_tokens):
                    continue
                # Reject methods / complex objects and values that clearly look like limits.
                if any(bad in norm for bad in ("max", "min", "limit", "required", "threshold")):
                    continue
                try:
                    displayed = _as_display_value(getattr(owner, attr))
                except Exception:
                    displayed = None
                if displayed is not None:
                    return displayed
    return "확인 불가"


def _format_account_summary(save, fallback_country="kr"):
    try:
        country = str(getattr(save, "cc", fallback_country) or fallback_country)
    except Exception:
        country = fallback_country
    try:
        version = str(getattr(save, "game_version", "확인 불가"))
    except Exception:
        version = "확인 불가"

    rank = _find_save_scalar(
        save,
        ("user_rank", "user_rank_value", "user_rank_total", "rank", "ur", "userRank"),
        ("userrank",),
    )
    catfood = _find_save_scalar(
        save,
        ("catfood", "cat_food", "cat_foods", "catfood_count", "cat_food_amount", "catfood_amount", "cat_food_count"),
        ("catfood", "cat_food"),
    )
    xp = _find_save_scalar(
        save,
        ("xp", "experience", "exp", "total_xp", "player_xp"),
        ("experience",),
    )
    try:
        cats = save.cats.get_all_cats()
        cat_count = f"{len(cats):,}"
    except Exception:
        cat_count = "확인 불가"

    return (
        f"• 국가: `{country}`\n"
        f"• 게임 버전: `{version}`\n"
        f"• 유저랭크: `{rank}`\n"
        f"• 통조림: `{catfood}`\n"
        f"• 경험치(XP): `{xp}`\n"
        f"• 캐릭터 수: `{cat_count}`"
    )


class TransferModal(discord.ui.Modal, title="냥코 세이브 불러오기"):
    transfer = discord.ui.TextInput(
        label="이어하기 코드",
        placeholder="게임에서 받은 이어하기 코드를 입력",
        required=True,
        max_length=64,
    )

    confirmation = discord.ui.TextInput(
        label="인증번호",
        placeholder="게임에서 받은 인증 번호를 입력",
        required=True,
        max_length=64,
    )

    country = discord.ui.TextInput(
        label="국가",
        placeholder="kr (한국)",
        default="kr",
        required=True,
        max_length=8,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id not in AUTHORIZED_USERS:
            await interaction.response.send_message(
                "🔒 먼저 /냥코에서 사용코드를 확인해 주세요.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 입력값은 화면/로그에 출력하지 않는다.
        try:
            handler = await asyncio.to_thread(
                load_save_sync,
                self.transfer.value,
                self.confirmation.value,
                self.country.value,
            )
            sessions[interaction.user.id] = handler
            _add_history(interaction.user.id, "세이브 불러오기 성공", "세이브 세션을 열었음")

            # 불러오기에 성공한 코드도 로컬 복구용으로 보관한다.
            try:
                _save_recovery(
                    interaction.user.id,
                    self.country.value.strip().lower() or "kr",
                    self.transfer.value.strip(),
                    self.confirmation.value.strip(),
                )
            except Exception as recovery_exc:
                # A local recovery-file problem must not hide an otherwise loaded save.
                print(f"복구 정보 저장 실패: {type(recovery_exc).__name__}: {recovery_exc}")

            save = handler.save_file
            summary = _format_account_summary(
                save,
                fallback_country=self.country.value.strip().lower() or "kr",
            )

            await interaction.followup.send(
                "✅ **세이브를 불러왔습니다.**\n\n"
                + summary + "\n\n"
                "아래 `▶️ 이용하기`를 눌러 편집 메뉴를 여세요.",
                view=LoadedView(),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                "❌ 세이브를 불러오지 못했습니다.\n"
                f"`{type(e).__name__}: {e}`",
                ephemeral=True,
            )


MULTI_QUANTITY_CATEGORIES = {"아이템", "기타 아이템", "개다래 열매", "개다래 씨앗", "수석", "수석 결정"}


class MultiQuantityModal(discord.ui.Modal, title="여러 항목 수량 입력"):
    amount = discord.ui.TextInput(
        label="선택한 모든 항목에 적용할 수량",
        placeholder="예: 999999",
        required=True,
        max_length=21,
    )

    def __init__(self, item_names: list[str]):
        super().__init__()
        self.item_names = list(item_names)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount.value.replace(",", "").strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ 수량은 0 이상의 숫자로 입력하세요.", ephemeral=True)
            return
        value = int(raw)
        if value > MAX_QTY:
            await interaction.response.send_message(
                f"❌ 최대 수량은 `{MAX_QTY:,}` (9000경)입니다.", ephemeral=True
            )
            return
        handler = sessions.get(interaction.user.id)
        if handler is None:
            await interaction.response.send_message("❌ 먼저 `📥 불러오기`를 해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        succeeded: list[str] = []
        failed: list[str] = []
        for name in self.item_names:
            try:
                await asyncio.to_thread(edit_item_sync, handler, name, value)
                succeeded.append(name)
            except Exception as exc:
                failed.append(f"{name} ({type(exc).__name__})")
        if succeeded:
            modified_sessions.add(interaction.user.id)
        lines = [f"✅ 적용 완료: **{len(succeeded)}개**"]
        if succeeded:
            lines.append("• " + ", ".join(succeeded[:12]) + (" …" if len(succeeded) > 12 else ""))
        if failed:
            lines.append(f"⚠️ 적용할 수 없는 항목: **{len(failed)}개**")
            lines.append("• " + ", ".join(failed[:8]) + (" …" if len(failed) > 8 else ""))
        if succeeded:
            lines.append("\n💾 `저장·업로드` 버튼을 눌러 변경 사항을 저장하세요.")
        await interaction.followup.send(
            "\n".join(lines),
            view=UploadOnlyView() if succeeded else None,
            ephemeral=True,
        )


class MultiItemSelect(discord.ui.Select):
    def __init__(self, category: str):
        self.category = category
        options = [discord.SelectOption(label=name[:100], value=name) for name in CATEGORIES[category][:25]]
        super().__init__(
            placeholder="한 번에 적용할 항목을 여러 개 선택하세요",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MultiQuantityModal(self.values))


class MultiItemView(discord.ui.View):
    def __init__(self, category: str):
        super().__init__(timeout=300)
        self.add_item(MultiItemSelect(category))


class MultiActionSelect(discord.ui.Select):
    """여러 항목을 골라 각 항목의 실제 처리 경로로 실행한다."""
    def __init__(self, category: str):
        self.category = category
        options = [discord.SelectOption(label=name[:100], value=name) for name in CATEGORIES[category][:25]]
        super().__init__(
            placeholder="실행할 기능을 여러 개 선택하세요",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        handler = sessions.get(interaction.user.id)
        if handler is None:
            await interaction.response.send_message("❌ 먼저 📥 불러오기를 해주세요.", ephemeral=True)
            return
        selected = list(self.values)
        await interaction.response.defer(ephemeral=True, thinking=True)
        succeeded: list[str] = []
        failed: list[str] = []
        needs_manual: list[str] = []

        # Snapshot the in-memory object before applying a batch. Persistent backup is
        # best-effort here; the backup button reports persistence failures explicitly.
        try:
            save_snapshots[interaction.user.id] = copy.deepcopy(handler)
        except Exception:
            pass

        interactive = {
            "캐릭터 ID로 확인", "캐릭터 이름으로 찾기", "전체 레벨 설정",
            "전체 특정 본능 MAX", "캐릭터 가격 수정", "소환 쿨타임 수정",
            "조수 슬롯/조수 편집", "탐험 시간", "보상 설정", "계정 편의 설정",
            "가마토토 만렙",
        }
        for name in selected:
            if name in interactive:
                needs_manual.append(name)
                continue
            try:
                result = await asyncio.to_thread(_run_multi_action_sync, handler, name)
                succeeded.append(f"{name} ({result})" if result else name)
            except Exception as exc:
                failed.append(f"{name} ({type(exc).__name__}: {str(exc)[:100]})")

        if succeeded:
            modified_sessions.add(interaction.user.id)
        lines = [f"✅ 일괄 실행 완료: **{len(succeeded)}개**"]
        if succeeded:
            lines.append("• " + ", ".join(succeeded[:8]) + (" …" if len(succeeded) > 8 else ""))
        if failed:
            lines.append(f"❌ 실행 실패: **{len(failed)}개**")
            lines.append("• " + "; ".join(failed[:5]) + (" …" if len(failed) > 5 else ""))
        if needs_manual:
            lines.append("📝 개별 입력이 필요한 기능 (이번 일괄 실행에서 제외): " + ", ".join(needs_manual[:8]))
        if succeeded:
            lines.append("\n💾 변경 사항은 `저장·업로드`를 눌러 저장하세요.")
        await interaction.followup.send(
            "\n".join(lines),
            view=UploadOnlyView() if succeeded else None,
            ephemeral=True,
        )


class MultiActionView(discord.ui.View):
    def __init__(self, category: str):
        super().__init__(timeout=300)
        self.add_item(MultiActionSelect(category))


class QuantityModal(discord.ui.Modal, title="수량 입력"):
    amount = discord.ui.TextInput(
        label="수량",
        placeholder="예: 500000",
        required=True,
        max_length=21,
    )

    def __init__(self, item_name: str):
        super().__init__()
        self.item_name = item_name

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount.value.replace(",", "").strip()

        if not raw.isdigit():
            await interaction.response.send_message(
                "❌ 숫자만 입력하세요.",
                ephemeral=True,
            )
            return

        value = int(raw)

        if value > MAX_QTY:
            await interaction.response.send_message(
                f"❌ 최대 수량은 `{MAX_QTY:,}` (9000경)입니다.",
                ephemeral=True,
            )
            return

        if value < 0:
            await interaction.response.send_message(
                "❌ 0 이상의 숫자를 입력하세요.",
                ephemeral=True,
            )
            return

        handler = sessions.get(interaction.user.id)
        if handler is None:
            await interaction.response.send_message(
                "❌ 먼저 `📥 불러오기`를 해주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await asyncio.to_thread(
                edit_item_sync,
                handler,
                self.item_name,
                value,
            )

            modified_sessions.add(interaction.user.id)

            # 설정 완료 메시지와 항목/수량 메시지를 분리한다.
            # 이렇게 하면 저장·업로드 버튼이 설정 완료 바로 아래에 표시된다.
            await interaction.followup.send(
                "✅ **설정값이 입력되었습니다.**\n"
                f"📌 **항목: {self.item_name}**\n"
                f"🔢 **수량: {value:,}**",
                view=UploadOnlyView(),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                "❌ 수정에 실패했습니다.\n"
                f"`{type(e).__name__}: {e}`",
                ephemeral=True,
            )


def _set_list_index(obj, attr_names, index, value):
    for attr in attr_names:
        arr = getattr(obj, attr, None)
        if isinstance(arr, list) and 0 <= index < len(arr):
            arr[index] = value
            return attr
    raise ValueError(f"연결된 저장 필드를 찾지 못했습니다: {attr_names}")


def get_cat_info_sync(handler, cat_id: int) -> tuple[int, str, bool]:
    save = handler.save_file
    cats = save.cats.get_all_cats()
    if not (0 <= cat_id < len(cats)):
        raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
    cat = cats[cat_id]

    # BCSFE 3.6.x는 실제 게임 데이터의 Unit_Explanation 파일에서
    # 캐릭터 이름을 읽는 get_names_cls()를 제공한다.
    names = cat.get_names_cls(save)
    if not names:
        name = f"알 수 없는 캐릭터 (ID {cat_id})"
    else:
        # 첫 번째 이름은 해당 캐릭터의 기본 이름이다.
        name = names[0].strip() or f"알 수 없는 캐릭터 (ID {cat_id})"
    return cat_id, name, bool(cat.unlocked)


def set_cat_owned_sync(handler, cat_id: int, owned: bool) -> str:
    save = handler.save_file
    cats = save.cats.get_all_cats()
    if not (0 <= cat_id < len(cats)):
        raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
    cat = cats[cat_id]
    if owned:
        cat.unlock(save)
        action = "획득"
    else:
        # BCSFE 공식 Cat.remove()를 사용해 해금 상태와 관련 플래그/드롭을 정리한다.
        cat.remove(reset=True, save_file=save)
        action = "삭제"
    return action


def _normalise_cat_name(name: object) -> str:
    """비교용 캐릭터 이름 정리: 공백만 제거하고 문자는 보존한다."""
    return "".join(str(name).split())


def _remove_neko_cheater_from_save(save) -> int:
    """전체 캐릭터 편집을 시작할 때 이름이 정확히 ネコチーター인 캐릭터를 제거한다.

    BCSFE 공식 Cat.remove() 경로를 사용한다. 이름을 확인할 수 없거나 제거가
    실패하면 성공으로 가장하지 않고 명시적으로 오류를 올린다.
    """
    target = _normalise_cat_name("ネコチーター")
    removed = 0
    failures: list[str] = []
    for cat in list(save.cats.get_all_cats()):
        try:
            names = cat.get_names_cls(save) or []
        except Exception:
            names = []
        # BCSFE uses zero-based unit IDs: ネコチーター is ID 673 (game list #674).
        # ID fallback handles KR/EN locale data where the Japanese name is untranslated.
        is_target = int(getattr(cat, "id", -1)) == 673 or any(
            _normalise_cat_name(name) == target for name in names
        )
        if not is_target:
            continue
        try:
            cat.remove(reset=True, save_file=save)
            removed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
    if failures:
        raise RuntimeError("ネコチーター 자동 삭제 실패: " + "; ".join(failures[:3]))
    return removed


def _get_all_cats_for_edit(handler: ServerHandler):
    """전체 캐릭터 편집 전 문제 캐릭터를 제거하고 최신 목록을 다시 읽는다."""
    save = handler.save_file
    LAST_BULK_FAILURES[id(handler)] = []
    removed = _remove_neko_cheater_from_save(save)
    LAST_NEKO_CHEATER_REMOVALS[id(handler)] = removed
    return save.cats.get_all_cats()


def _neko_removal_notice(handler: ServerHandler) -> str:
    removed = LAST_NEKO_CHEATER_REMOVALS.pop(id(handler), 0)
    failures = LAST_BULK_FAILURES.pop(id(handler), [])
    if removed:
        note = f"\n🗑️ `ネコチーター` 자동 삭제: **{removed}개**"
    else:
        note = "\n🔎 `ネコチーター` 자동 삭제 대상이 별도로 확인되지 않았습니다."
    if failures:
        note += f"\n⚠️ 일부 캐릭터 적용 실패: **{len(failures)}개** — " + "; ".join(failures[:3])
    return note


def _unlock_highest_available_form(save, cat, picture_book=None) -> bool:
    """해당 캐릭터가 지원하는 최고 진화(3진화/4진화)를 해금한다."""
    if picture_book is None:
        picture_book = save.cats.read_nyanko_picture_book(save)
    pdata = picture_book.get_cat(cat.id)
    total_forms = int(pdata.total_forms) if pdata is not None else 0
    if total_forms < 3:
        return False
    cat.unlock(save)
    # 먼저 3진화를 해금한 뒤, 지원되는 경우 4번째 폼도 해금한다.
    cat.true_form(save, set_current_form=True)
    if total_forms >= 4:
        cat.unlock_fourth_form(save, set_current_form=True)
    return True


def edit_cats_sync(handler, mode: str, cat_id: int | None = None) -> int:
    save = handler.save_file
    if cat_id is not None:
        cats = save.cats.get_all_cats()
        if not (0 <= cat_id < len(cats)):
            raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
        targets = [cats[cat_id]]
    else:
        # 전체 캐릭터를 대상으로 할 때만 네코 치터 자동 정리를 실행한다.
        targets = _get_all_cats_for_edit(handler)

    picture_book = None
    if mode in ("evolve", "all"):
        picture_book = save.cats.read_nyanko_picture_book(save)

    changed = 0
    failures: list[str] = []
    for cat in targets:
        try:
            if mode in ("unlock", "all"):
                cat.unlock(save)
            if mode in ("max", "all"):
                cat.upgrade.base = max(1, int(cat.max_upgrade_level.base))
                cat.upgrade.plus = max(0, int(cat.max_upgrade_level.plus))
                if not cat.unlocked:
                    cat.unlock(save)
            if mode == "evolve":
                if not _unlock_highest_available_form(save, cat, picture_book):
                    continue
                changed += 1
                continue
            if mode == "all":
                _unlock_highest_available_form(save, cat, picture_book)
            changed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")

    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else "진화 데이터가 있는 캐릭터를 찾지 못했습니다."
        raise ValueError(f"전체 캐릭터 수정 적용 0개. {detail}")
    return changed


def edit_story_sync(handler, item: str) -> int:
    """Edit story/treasure progress without requiring treasure constants for unrelated actions."""
    save = handler.save_file
    chapters = save.story.get_real_chapters()
    if item == "보물 최고급":
        max_treasure = 60_000_000
        changed = 0
        for chapter in chapters:
            for stage in chapter.get_valid_treasure_stages():
                stage.set_treasure(max_treasure)
                changed += 1
        if changed == 0:
            raise ValueError("보물 스테이지를 찾지 못했습니다.")
        return changed

    chapter_ids = {"세계편": [0, 1, 2], "미래편": [3, 4, 5], "우주편": [6, 7, 8]}
    if item in chapter_ids:
        changed = 0
        for cid in chapter_ids[item]:
            if cid >= len(chapters):
                continue
            for stage in chapters[cid].get_valid_treasure_stages():
                # Story categories in this UI refer to treasure levels, not clearing stages.
                # Leave each stage at the library's supported maximum only when available.
                manager = getattr(core.core_data, "max_value_manager", None)
                max_treasure = getattr(manager, "treasure_level", None) if manager is not None else None
                if max_treasure is None:
                    max_treasure = getattr(core.core_data, "treasure_level_max", None)
                if max_treasure is None:
                    raise ValueError("현재 BCSFE 버전에서 보물 최대 레벨 값을 찾지 못했습니다. 세이브를 변경하지 않았습니다.")
                stage.set_treasure(max_treasure)
                changed += 1
        if changed == 0:
            raise ValueError(f"{item}의 보물 스테이지를 찾지 못했습니다.")
        return changed

    if item == "전체 클리어":
        changed = 0
        for chapter in chapters:
            try:
                valid = chapter.get_valid_treasure_stages()
                for sid, _stage in enumerate(valid):
                    chapter.clear_stage(sid, 1)
                chapter.progress = max(int(chapter.progress), len(chapter.stages))
                changed += 1
            except Exception as exc:
                LAST_BULK_FAILURES.setdefault(id(handler), []).append(
                    f"스토리 {getattr(chapter, 'id', '?')}: {type(exc).__name__}: {exc}"
                )
        if changed == 0:
            raise ValueError("클리어 가능한 스토리 챕터가 없습니다.")
        return changed

    if item == "레전드 스토리":
        changed = 0
        failures = []
        for chapter in chapters:
            try:
                chapter.progress = max(int(chapter.progress), len(chapter.stages))
                changed += 1
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
        LAST_BULK_FAILURES[id(handler)] = failures
        if changed == 0:
            raise ValueError("레전드 스토리 진행도를 변경하지 못했습니다. 현재 세이브 구조를 확인하세요.")
        return changed
    raise ValueError("알 수 없는 스토리·보물 항목입니다.")


def edit_item_sync(handler, item: str, value: int) -> None:
    save = handler.save_file
    if item in SCALAR_FIELDS:
        setattr(save, SCALAR_FIELDS[item], value); return

    # 일반 전투 아이템: BCSFE의 battle_items 구조를 이용
    battle_names = {
        "스피드 업":0, "트레저 레이더":1, "고양이 도령":2,
        "야옹컴":3, "고양이 박사":4, "스냥이퍼":5,
    }
    if item in battle_names:
        bi = save.battle_items
        idx = battle_names[item]
        for attr in ("items", "item_amounts", "values"):
            arr = getattr(bi, attr, None)
            if isinstance(arr, list) and idx < len(arr):
                arr[idx] = value; return
        raise ValueError("전투 아이템 저장 구조를 찾지 못했습니다.")

    # 개다래 / 개다래 씨앗은 BCSFE SaveFile의 catfruit 배열을 직접 사용
    fruit = {
        "초록 개다래":0,"보라 개다래":1,"빨강 개다래":2,"파랑 개다래":3,
        "노랑 개다래":4,"무지개 개다래":5,"고대 개다래":6,"악마 개다래":7,"황금 개다래":8,
        "초록 씨앗":9,"보라 씨앗":10,"빨강 씨앗":11,"파랑 씨앗":12,
        "노랑 씨앗":13,"무지개 씨앗":14,"고대 씨앗":15,"악마 씨앗":16,"황금 씨앗":17,
    }
    if item in fruit:
        arr = getattr(save, "catfruit", None)
        if not isinstance(arr, list) or fruit[item] >= len(arr):
            raise ValueError("현재 세이브 버전의 개다래 배열을 확인할 수 없습니다.")
        arr[fruit[item]] = value; return

    catseye = {
        "캣츠아이 EX":0,"캣츠아이 레어":1,"캣츠아이 슈퍼 레어":2,
        "캣츠아이 울트라 슈퍼 레어":3,"캣츠아이 레전드":4,"캣츠아이 다크":5,
    }
    if item in catseye:
        arr = getattr(save, "catseyes", None)
        if not isinstance(arr, list) or catseye[item] >= len(arr):
            raise ValueError("현재 세이브 버전의 캣츠아이 배열을 확인할 수 없습니다.")
        arr[catseye[item]] = value; return

    if item in ("자수석","홍수석","청수석","녹수석","황수석","무지개 수석",
                "자수석 결정","홍수석 결정","청수석 결정","녹수석 결정","황수석 결정"):
        # 수석/결정은 BCSFE의 scheme_items에 버전별로 들어가므로 알려진 수치 필드를 탐색
        obj = getattr(save, "scheme_items", None)
        if obj is not None:
            # Do not blindly overwrite the first scheme item: it may be a different
            # stone type. Only edit an entry when the save object exposes an explicit
            # matching name/id field; numeric IDs vary by BCSFE/game-data version.
            target_norm = "".join(item.split()).lower()
            for attr in ("items", "scheme_items", "values"):
                arr = getattr(obj, attr, None)
                if not isinstance(arr, list):
                    continue
                for entry in arr:
                    labels = [getattr(entry, key, None) for key in ("name", "display_name", "text", "key")]
                    labels = ["".join(str(x).split()).lower() for x in labels if x is not None]
                    if target_norm in labels and hasattr(entry, "amount"):
                        entry.amount = value
                        return
        raise ValueError("이 BCSFE 세이브에서 해당 수석의 개별 ID를 확인하지 못했습니다. 다른 수석을 잘못 변경하지 않도록 적용을 중단했습니다.")

    if item == "가마토토 만렙":
        g = getattr(save, "gamatoto", None)
        for attr in ("level", "gamatoto_level"):
            if hasattr(g, attr): setattr(g, attr, value); return
        raise ValueError("가마토토 레벨 필드를 찾지 못했습니다.")

    if item == "골드패스":
        op = getattr(save, "officer_pass", None)
        for attr in ("gold_pass", "has_gold_pass", "enabled"):
            if hasattr(op, attr): setattr(op, attr, bool(value)); return
        raise ValueError("골드패스 필드를 찾지 못했습니다.")

    raise ValueError(f"'{item}'의 실제 저장 필드를 찾지 못했습니다.")



def set_cat_level_sync(handler: ServerHandler, cat_id: int, base_level: int | None, plus_level: int | None) -> tuple[str, int | None, int | None]:
    save = handler.save_file
    cats = save.cats.get_all_cats()
    if not (0 <= cat_id < len(cats)):
        raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
    if base_level is None and plus_level is None:
        raise ValueError("기본 레벨 또는 플러스 레벨 중 하나는 입력하세요.")
    if base_level is not None and base_level < 1:
        raise ValueError("기본 레벨은 1 이상으로 입력하세요.")
    if plus_level is not None and plus_level < 0:
        raise ValueError("플러스 레벨은 0 이상으로 입력하세요.")
    cat = cats[cat_id]
    # BCSFE가 제공하는 해당 캐릭터의 실제 최대치를 사용합니다.
    actual_base = max(1, int(cat.max_upgrade_level.base))
    actual_plus = max(0, int(cat.max_upgrade_level.plus))
    if not cat.unlocked:
        cat.unlock(save)
    applied_base = None if base_level is None else min(base_level, actual_base)
    applied_plus = None if plus_level is None else min(plus_level, actual_plus)
    if applied_base is not None:
        cat.upgrade.base = applied_base
    if applied_plus is not None:
        cat.upgrade.plus = applied_plus
    return "레벨 설정", applied_base, applied_plus


def set_cat_third_form_sync(handler: ServerHandler, cat_id: int) -> str:
    save = handler.save_file
    cats = save.cats.get_all_cats()
    if not (0 <= cat_id < len(cats)):
        raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
    cat = cats[cat_id]
    picture_book = save.cats.read_nyanko_picture_book(save)
    pdata = picture_book.get_cat(cat.id)
    if pdata is None or int(pdata.total_forms) < 3:
        raise ValueError("이 캐릭터는 3진화 데이터가 없습니다.")
    cat.unlock(save)
    cat.true_form(save, set_current_form=True)
    return "3진화 해방"


def set_cat_fourth_form_sync(handler: ServerHandler, cat_id: int) -> str:
    save = handler.save_file
    cats = save.cats.get_all_cats()
    if not (0 <= cat_id < len(cats)):
        raise ValueError(f"캐릭터 ID 범위가 아닙니다. 현재 최대 ID: {len(cats)-1}")
    cat = cats[cat_id]
    picture_book = save.cats.read_nyanko_picture_book(save)
    pdata = picture_book.get_cat(cat.id)
    if pdata is None or int(pdata.total_forms) < 4:
        raise ValueError("이 캐릭터는 4진화 데이터가 없습니다.")
    cat.unlock(save)
    # 4진화는 3진화 선행 해금 후 적용한다.
    cat.true_form(save, set_current_form=True)
    cat.unlock_fourth_form(save, set_current_form=True)
    return "4진화 해방"


def set_all_talents_sync(handler: ServerHandler, max_level: bool = True) -> int:
    save = handler.save_file
    cats = _get_all_cats_for_edit(handler)
    talent_data = save.cats.read_talent_data(save)
    if talent_data is None:
        raise ValueError("본능 데이터를 불러오지 못했습니다.")
    changed = 0
    failures: list[str] = []
    for cat in cats:
        try:
            if not cat.unlocked:
                cat.unlock(save)
            if cat.talents is None:
                continue
            for talent in cat.talents:
                skill = talent_data.get_skill_from_cat(cat.id, talent.id)
                if skill is None:
                    continue
                target = int(skill.max_lv) if max_level else 1
                if target <= 0:
                    continue
                talent.level = target
                changed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
            continue
    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else "적용할 본능 데이터가 없습니다."
        raise ValueError(detail)
    return changed


def get_all_talent_names_sync(handler: ServerHandler) -> list[str]:
    save = handler.save_file
    talent_data = save.cats.read_talent_data(save)
    if talent_data is None:
        raise ValueError("본능 데이터를 불러오지 못했습니다.")
    names: dict[str, str] = {}
    for cat in save.cats.get_all_cats():
        try:
            cat_skill = talent_data.get_cat_skill(cat.id)
            if cat_skill is None:
                continue
            for skill in cat_skill.skills:
                name = talent_data.get_skill_name(skill.text_id)
                if not name:
                    continue
                name = name.split("<br>")[0].strip()
                if name:
                    names[name] = name
        except Exception:
            continue
    return sorted(names.values())


def set_all_specific_talent_max_sync(handler: ServerHandler, talent_name: str) -> int:
    save = handler.save_file
    cats = _get_all_cats_for_edit(handler)
    talent_data = save.cats.read_talent_data(save)
    if talent_data is None:
        raise ValueError("본능 데이터를 불러오지 못했습니다.")
    target_name = talent_name.strip()
    changed = 0
    failures: list[str] = []
    for cat in cats:
        try:
            cat_skill = talent_data.get_cat_skill(cat.id)
            if cat_skill is None or cat.talents is None:
                continue
            matched = False
            for skill in cat_skill.skills:
                name = talent_data.get_skill_name(skill.text_id)
                if not name:
                    continue
                name = name.split("<br>")[0].strip()
                if name != target_name:
                    continue
                talent = cat.get_talent_from_id(skill.ability_id)
                if talent is None:
                    continue
                max_lv = int(skill.max_lv) or 1
                talent.level = max_lv
                changed += 1
                matched = True
                break
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
            continue
    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else f"`{target_name}` 본능을 가진 캐릭터를 찾지 못했습니다."
        raise ValueError(detail)
    return changed


class SpecificTalentSelectView(discord.ui.View):
    def __init__(self, names: list[str]):
        super().__init__(timeout=120)
        options = [
            discord.SelectOption(label=name[:100], value=name)
            for name in names[:25]
        ]
        self.select = discord.ui.Select(
            placeholder="MAX로 설정할 본능을 선택하세요",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        name = self.select.values[0]
        handler = sessions.get(interaction.user.id)
        if handler is None:
            await interaction.response.send_message("❌ 먼저 📥 불러오기를 해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            n = await asyncio.to_thread(set_all_specific_talent_max_sync, handler, name)
            modified_sessions.add(interaction.user.id)
            cleanup_note = _neko_removal_notice(handler)
            await interaction.followup.send(
                f"✅ 전체 캐릭터의 **{name}** 본능을 MAX로 설정했습니다. ({n}개){cleanup_note}\n\n"
                "💾 저장·업로드 후 새 코드를 게임에서 입력해야 실제 반영됩니다.",
                view=UploadOnlyView(), ephemeral=True
            )
        except Exception as e:
            removed = LAST_NEKO_CHEATER_REMOVALS.pop(id(handler), 0)
            failures = LAST_BULK_FAILURES.pop(id(handler), [])
            if removed:
                modified_sessions.add(interaction.user.id)
                await interaction.followup.send(
                    f"⚠️ 본능 설정은 실패했지만 `ネコチーター` {removed}개는 삭제됐습니다.\n"
                    f"오류: `{type(e).__name__}: {e}`",
                    view=UploadOnlyView(), ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ 본능 설정 실패: `{type(e).__name__}: {e}`", ephemeral=True)


def set_all_form_sync(handler: ServerHandler, form: int) -> int:
    if form not in (3, 4):
        raise ValueError("진화 단계는 3 또는 4만 지원합니다.")
    save = handler.save_file
    cats = _get_all_cats_for_edit(handler)
    picture_book = save.cats.read_nyanko_picture_book(save)
    changed = 0
    failures: list[str] = []
    for cat in cats:
        try:
            pdata = picture_book.get_cat(cat.id)
            total_forms = int(pdata.total_forms) if pdata is not None else 0
            if total_forms < form:
                continue
            cat.unlock(save)
            if total_forms >= 3:
                cat.true_form(save, set_current_form=True)
            if form == 4:
                cat.unlock_fourth_form(save, set_current_form=True)
            changed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else f"{form}진화가 가능한 캐릭터를 찾지 못했습니다."
        raise ValueError(f"전체 {form}진화 적용 0개. {detail}")
    return changed


def set_all_level_sync(handler: ServerHandler, base_level: int | None, plus_level: int | None) -> int:
    if base_level is None and plus_level is None:
        raise ValueError("기본 레벨 또는 플러스 레벨 중 하나 이상 입력하세요.")
    if base_level is not None and base_level < 1:
        raise ValueError("기본 레벨은 1 이상으로 입력하세요.")
    if plus_level is not None and plus_level < 0:
        raise ValueError("플러스 레벨은 0 이상으로 입력하세요.")

    save = handler.save_file
    cats = _get_all_cats_for_edit(handler)
    changed = 0
    failures: list[str] = []
    for cat in cats:
        try:
            max_base = max(1, int(cat.max_upgrade_level.base))
            max_plus = max(0, int(cat.max_upgrade_level.plus))
            if not cat.unlocked:
                cat.unlock(save)
            if base_level is not None:
                cat.upgrade.base = min(base_level, max_base)
            if plus_level is not None:
                cat.upgrade.plus = min(plus_level, max_plus)
            # 다시 읽어 실제 객체 값이 적용되었는지 검사한다.
            if base_level is not None and int(cat.upgrade.base) != min(base_level, max_base):
                raise RuntimeError("기본 레벨 값 확인 실패")
            if plus_level is not None and int(cat.upgrade.plus) != min(plus_level, max_plus):
                raise RuntimeError("플러스 레벨 값 확인 실패")
            changed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else "적용 가능한 캐릭터가 없습니다."
        raise ValueError(f"전체 레벨 설정 적용 0개. {detail}")
    return changed


def set_all_max_level_sync(handler: ServerHandler, plus: bool = False) -> int:
    save = handler.save_file
    cats = _get_all_cats_for_edit(handler)
    changed = 0
    failures: list[str] = []
    for cat in cats:
        try:
            if not cat.unlocked:
                cat.unlock(save)
            if plus:
                cat.upgrade.plus = max(0, int(cat.max_upgrade_level.plus))
            else:
                cat.upgrade.base = max(1, int(cat.max_upgrade_level.base))
            changed += 1
        except Exception as exc:
            failures.append(f"ID {getattr(cat, 'id', '?')}: {type(exc).__name__}: {exc}")
    LAST_BULK_FAILURES[id(handler)] = failures
    if changed == 0:
        detail = "; ".join(failures[:3]) if failures else "적용 가능한 캐릭터가 없습니다."
        raise ValueError(f"전체 최대 레벨 적용 0개. {detail}")
    return changed


class AllCharacterLevelModal(discord.ui.Modal, title="전체 캐릭터 레벨 설정"):
    base_level = discord.ui.TextInput(label="기본 레벨 (캐릭터별 최대치 적용)", placeholder="비워도 됨 (예: 60)", required=False, max_length=3)
    plus_level = discord.ui.TextInput(label="플러스 레벨 (캐릭터별 최대치 적용)", placeholder="비워도 됨 (예: 10)", required=False, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        def parse(v):
            v = v.value.replace(',', '').strip()
            if v == '':
                return None
            if not v.isdigit():
                raise ValueError("레벨은 숫자로 입력하세요.")
            return int(v)
        try:
            base = parse(self.base_level)
            plus = parse(self.plus_level)
            if base is None and plus is None:
                raise ValueError("기본 레벨 또는 플러스 레벨 중 하나 이상 입력하세요.")
            if base is not None and base < 1:
                raise ValueError("기본 레벨은 1 이상으로 입력하세요.")
            if plus is not None and plus < 0:
                raise ValueError("플러스 레벨은 0 이상으로 입력하세요.")
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True); return
        handler = sessions.get(interaction.user.id)
        if handler is None:
            await interaction.response.send_message("❌ 먼저 📥 불러오기를 해주세요.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            n = await asyncio.to_thread(set_all_level_sync, handler, base, plus)
            modified_sessions.add(interaction.user.id)
            cleanup_note = _neko_removal_notice(handler)
            parts=[]
            if base is not None: parts.append(f"기본 레벨 요청값 **{base}**")
            if plus is not None: parts.append(f"플러스 레벨 요청값 **{plus}**")
            await interaction.followup.send(
                f"✅ 전체 캐릭터 {n}개에 {' / '.join(parts)} 적용 완료{cleanup_note}\n"
                "캐릭터별 한도를 넘는 입력값은 해당 캐릭터의 최대값으로 적용했습니다.\n"
                "💾 저장·업로드 후 새 이어하기 코드와 인증번호를 게임에서 입력해야 실제 반영됩니다.",
                view=UploadOnlyView(), ephemeral=True
            )
        except Exception as e:
            removed = LAST_NEKO_CHEATER_REMOVALS.pop(id(handler), 0)
            failures = LAST_BULK_FAILURES.pop(id(handler), [])
            if removed:
                modified_sessions.add(interaction.user.id)
                await interaction.followup.send(
                    f"⚠️ 레벨 설정은 실패했지만 `ネコチーター` {removed}개는 삭제됐습니다.\n"
                    f"오류: `{type(e).__name__}: {e}`",
                    view=UploadOnlyView(), ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ 전체 레벨 설정 실패: `{type(e).__name__}: {e}`", ephemeral=True)


def set_cat_talents_sync(handler: ServerHandler, cat_id: int, max_level: bool = True) -> tuple[str, int]:
    save = handler.save_file
def _run_multi_action_sync(handler: ServerHandler, item: str) -> str:
    """Execute multi-select-safe actions using the same handlers as single-select."""
    if item in ("전체 해금", "전체 만렙", "전체 진화", "전체 해금 + 만렙 + 진화"):
        mode = {"전체 해금": "unlock", "전체 만렙": "max", "전체 진화": "evolve", "전체 해금 + 만렙 + 진화": "all"}[item]
        return f"{edit_cats_sync(handler, mode)}개 적용"
    if item == "전체 본능 해방":
        return f"{set_all_talents_sync(handler, False)}개 적용"
    if item == "전체 본능 MAX":
        return f"{set_all_talents_sync(handler, True)}개 적용"
    if item == "전체 3진화":
        return f"{set_all_form_sync(handler, 3)}개 적용"
    if item == "전체 4진화":
        return f"{set_all_form_sync(handler, 4)}개 적용"
    if item == "전체 기본레벨 MAX":
        return f"{set_all_max_level_sync(handler, False)}개 적용"
    if item == "전체 플러스레벨 MAX":
        return f"{set_all_max_level_sync(handler, True)}개 적용"
