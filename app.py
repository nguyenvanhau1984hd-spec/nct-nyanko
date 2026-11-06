import os, secrets, traceback
from flask import Flask, jsonify, render_template, request, session
from editor_core import (
    CATEGORIES, load_save_sync, upload_sync, edit_item_sync, _run_multi_action_sync,
    set_cat_level_sync, get_cat_info_sync, set_cat_owned_sync, set_cat_third_form_sync,
    set_cat_fourth_form_sync, set_cat_talents_sync, set_all_specific_talent_max_sync,
    set_all_form_sync, set_all_level_sync, set_all_max_level_sync, set_all_talents_sync,
    get_all_talent_names_sync, edit_story_sync, _format_account_summary
)

app = Flask(__name__)
app.secret_key = os.getenv('NCT_SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
SESSIONS = {}


def sid():
    if 'sid' not in session:
        session['sid'] = secrets.token_urlsafe(24)
    return session['sid']


def handler():
    h = SESSIONS.get(sid())
    if h is None:
        raise ValueError('먼저 세이브를 불러오세요.')
    return h


@app.get('/')
def index():
    return render_template('index.html', categories=CATEGORIES)


@app.post('/api/load')
def api_load():
    try:
        data = request.get_json(force=True)
        country = str(data.get('country', 'kr')).strip().lower() or 'kr'
        transfer = str(data.get('transfer', '')).strip()
        confirm = str(data.get('confirmation', '')).strip()
        if not transfer or not confirm:
            return jsonify(ok=False, error='이어하기 코드와 인증번호를 입력하세요.'), 400
        h = load_save_sync(transfer, confirm, country)
        SESSIONS[sid()] = h
        return jsonify(ok=True, summary=_format_account_summary(h.save_file, country))
    except Exception as e:
        return jsonify(ok=False, error=f'{type(e).__name__}: {e}'), 400


@app.get('/api/status')
def api_status():
    h = SESSIONS.get(sid())
    if not h:
        return jsonify(ok=True, loaded=False)
    try:
        return jsonify(ok=True, loaded=True, summary=_format_account_summary(h.save_file, 'kr'))
    except Exception as e:
        return jsonify(ok=True, loaded=True, summary={'error': str(e)})


@app.post('/api/item')
def api_item():
    try:
        d=request.get_json(force=True); item=str(d['item']); value=int(d['value'])
        # Conservative UI limits for common quantities. BCSFE/game structures remain authoritative.
        if item in ('통조림','XP'): value=min(max(value,0),2_147_483_647)
        elif item=='NP': value=min(max(value,0),9_999)
        elif item in ('냥코 티켓','레어 티켓','플래티넘 티켓','플래티넘 조각','레전드 티켓','럭키 티켓','럭키 티켓G'): value=min(max(value,0),999)
        edit_item_sync(handler(), item, value)
        return jsonify(ok=True, message=f'{item}: {value:,} 적용 완료')
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/action')
def api_action():
    try:
        item=str(request.get_json(force=True)['item'])
        msg=_run_multi_action_sync(handler(), item)
        return jsonify(ok=True,message=f'{item}: {msg}')
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/story')
def api_story():
    try:
        item=str(request.get_json(force=True)['item'])
        n=edit_story_sync(handler(), item)
        return jsonify(ok=True,message=f'{item}: {n}개 적용 완료')
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/cat/level')
def api_cat_level():
    try:
        d=request.get_json(force=True)
        msg,b,p=set_cat_level_sync(handler(), int(d['id']), d.get('base'), d.get('plus'))
        return jsonify(ok=True,message=f'ID {int(d["id"])} → 기본 {b}, 플러스 {p}')
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/cat/info')
def api_cat_info():
    try:
        cat_id=int(request.get_json(force=True)['id'])
        a=get_cat_info_sync(handler(), cat_id)
        return jsonify(ok=True, info={'id':a[0],'name':a[1],'unlocked':a[2]})
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/cat/owned')
def api_cat_owned():
    try:
        d=request.get_json(force=True)
        return jsonify(ok=True,message=set_cat_owned_sync(handler(), int(d['id']), bool(d['owned'])))
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/cat/form')
def api_cat_form():
    try:
        d=request.get_json(force=True); cid=int(d['id']); form=int(d['form'])
        if form==3: msg=set_cat_third_form_sync(handler(),cid)
        elif form==4: msg=set_cat_fourth_form_sync(handler(),cid)
        else: raise ValueError('3진 또는 4진만 지원합니다.')
        return jsonify(ok=True,message=msg)
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.post('/api/save/upload')
def api_upload():
    try:
        codes=upload_sync(handler())
        return jsonify(ok=True,transfer=codes[0],confirmation=codes[1])
    except Exception as e:
        return jsonify(ok=False,error=f'{type(e).__name__}: {e}'),400


@app.get('/health')
def health():
    return 'ok', 200

if __name__ == '__main__':
    host=os.getenv('NCT_HOST','127.0.0.1')
    port=int(os.getenv('PORT','5000'))
    app.run(host=host,port=port,debug=False)


@app.post("/api/cat/talents")
def api_cat_talents():
    d = request.get_json(force=True)
    return jsonify({"message": set_cat_talents_sync(
        handler(), int(d["id"]), bool(d.get("max_level", True))
    )})

@app.get("/api/talents")
def api_talents():
    return jsonify({"talents": get_all_talent_names_sync(handler())})

@app.post("/api/cat/talent/max")
def api_cat_talent_max():
    d = request.get_json(force=True)
    count = set_all_specific_talent_max_sync(handler(), str(d["name"]))
    return jsonify({"message": f"{count}개 캐릭터에 적용했습니다.", "count": count})

@app.post("/api/cats/level/all")
def api_cats_level_all():
    d = request.get_json(force=True)
    count = set_all_level_sync(handler(), d.get("base"), d.get("plus"))
    return jsonify({"message": f"{count}개 캐릭터에 적용했습니다.", "count": count})

@app.post("/api/cats/level/max")
def api_cats_level_max():
    d = request.get_json(force=True)
    count = set_all_max_level_sync(handler(), bool(d.get("plus", False)))
    return jsonify({"message": f"{count}개 캐릭터에 적용했습니다.", "count": count})

@app.post("/api/cats/form/all")
def api_cats_form_all():
    d = request.get_json(force=True)
    count = set_all_form_sync(handler(), int(d["form"]))
    return jsonify({"message": f"{count}개 캐릭터에 적용했습니다.", "count": count})

@app.post("/api/cats/talents/all")
def api_cats_talents_all():
    d = request.get_json(force=True)
    count = set_all_talents_sync(handler(), bool(d.get("max_level", True)))
    return jsonify({"message": f"{count}개 캐릭터에 적용했습니다.", "count": count})
