import os, re, html, unicodedata, urllib.parse, math, io
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text as _sql_text
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, NextPageTemplate, PageBreak
import plotly.express as px
import psycopg2
st.set_page_config(
    page_title="Foreign Media Monitoring - DEMP",
    page_icon="https://raw.githubusercontent.com/Rugger85/DEMP-FR/main/logo.jpeg",
    layout="wide"
)



THEME={
    "bg":"#0a0f1f",
    "bg_grad_from":"#0a0f1f",
    "bg_grad_to":"#0e1b33",
    "card":"#0e1629cc",
    "ink":"#e6edf3",
    "muted":"#9fb3c8",
    "accent":"#5dd6ff",
    "border":"#1b2740",
    "link":"#7dc3ff",
    "desc":"#7ee3ff",
    "card_bg":"#0f1a30",
    "desc_label":"#8fd3ff"
}

PDF_COLORS={
    "ink":"#0e1629",
    "muted":"#334155",
    "accent":"#1d4ed8",
    "desc":"#0ea5e9",
    "border":"#cbd5e1",
    "card":"#f1f5f9",
    "card_alt":"#e2e8f0",
    "demp":"#ff4d4d",
    "band":"#0e1629",
    "band_text":"#ffffff"
}

def normalize_text(t):
    if not isinstance(t, str): return ""
    t = html.unescape(t)
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[^\w\s\-\.,'&:/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.lower()

def _norm_key(sr: pd.Series) -> pd.Series:
    return (sr.astype(str).str.normalize("NFKC").str.replace(r"\s+", " ", regex=True).str.strip().str.lower())

def _norm_topic_val(t: str) -> str:
    if not isinstance(t, str): return ""
    return re.sub(r"\s+", " ", t).strip().lower()

def _norm_url(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower().str.replace(r"/+$", "", regex=True)

def _fmt_num(n:int)->str:
    try:n=int(n)
    except:return"—"
    if n>=1_000_000:return f"{n/1_000_000:.1f}M"
    if n>=1_000:return f"{n/1_000:.1f}K"
    return str(n)

def _fmt_count(v):
    if v is None or v=="": return "—"
    try: n=int(v)
    except:
        try: n=int(float(v))
        except: return "—"
    if n>=1_000_000: return f"{n/1_000_000:.1f}M"
    if n>=1_000: return f"{n/1_000:.1f}K"
    return str(n)

def is_pk_topic(text:str)->bool:
    if not isinstance(text,str):return False
    t=text.lower()
    return bool(re.search(r"\bpakistan\b",t)) or ("پاکستان" in text)

def render_title_ticker(rows: pd.DataFrame, title: str, ticker_speed: int = 80, row_gap: int = 12, seamless_scroll: bool = False, height: int = 140):
    if rows.empty:
        st.info(f"No rows for {title}.")
        return
    work = rows.copy()
    for c in ["title","channel_title","channel_thumb","url","published_at","video_id"]:
        if c not in work.columns: work[c] = ""
    work["published_at"] = pd.to_datetime(work["published_at"], errors="coerce")
    work = work.sort_values("published_at", ascending=False)
    cards=[]
    for _, r in work.iterrows():
        vid_title  = str(r.get("title","")).strip()
        ch_name    = str(r.get("channel_title","")).strip()
        ch_logo    = str(r.get("channel_thumb","")).strip()
        url        = str(r.get("url","")).strip()
        ts         = r.get("published_at")
        latest_str = ts.strftime("%Y-%m-%d %H:%M") if pd.notna(ts) else ""
        title_html  = (f'<a href="{html.escape(url)}" target="_blank" style="text-decoration:none;color:{THEME["link"]};">{html.escape(vid_title)}</a>') if url else html.escape(vid_title)
        ext_html    = (f' <a href="{html.escape(url)}" target="_blank" title="Open on YouTube" style="text-decoration:none;color:{THEME["muted"]};">↗</a>') if url else ""
        logo_html   = (f'<img src="{html.escape(ch_logo)}" loading="lazy" referrerpolicy="no-referrer" title="{html.escape(ch_name)}" alt="{html.escape(ch_name)}" style="width:20px;height:20px;border-radius:50%;object-fit:cover;margin-right:6px;border:1px solid rgba(255,255,255,0.15)"/>') if ch_logo else ""
        cards.append(f'<div class="card"><div class="col date">{latest_str}</div><div class="col topic">{title_html}{ext_html}</div><div class="col ch">{logo_html}<span class="ch-name">{html.escape(ch_name)}</span></div></div>')
    cards_html="".join(cards)
    duplicate=(seamless_scroll and len(cards)>=2)
    inner_html=cards_html+cards_html if duplicate else cards_html
    animate_css="animation: scroll linear var(--duration) infinite;" if duplicate else ""
    html_str=f"""<!doctype html><html><head><meta charset="utf-8"/><style>
    :root{{--bg:{THEME['bg']};--card:{THEME['card']};--ink:{THEME['ink']};--muted:{THEME['muted']};--accent:{THEME['accent']};--gap:{row_gap}px;--duration:60s;}}
    body{{margin:0;background:transparent; 0%, {THEME['bg_grad_to']} 100%)}}
    .wrap{{margin:4px 0 10px 0}}
    .title{{color:{THEME['ink']};font-weight:800;margin:0 0 6px 4px;font-size:1.05rem;letter-spacing:.2px}}
    .ticker-wrap{{width:100%;overflow:hidden;background:transparent;border-radius:14px;border:1px solid rgba(255,255,255,0.08);backdrop-filter:blur(16px)}}
    .ticker{{display:inline-flex;gap:var(--gap);align-items:stretch;padding:8px 10px;{animate_css}will-change:transform}}
    @keyframes scroll{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
    .card{{display:grid;grid-template-columns:180px 760px 280px;gap:10px;min-width:1240px;padding:8px 10px;background:var(--card);color:var(--ink);border:1px solid rgba(255,255,255,0.07);border-radius:10px;box-shadow:0 8px 22px rgba(2,6,23,.35)}}
    .col{{display:flex;align-items:center;color:var(--ink)}}
    .topic{{font-weight:700;font-size:1.02rem}}
    .ch .ch-name{{font-weight:600;margin-left:4px}}
    .date{{color:{THEME['muted']};font-variant-numeric:tabular-nums}}
    .ticker:hover{{animation-play-state:paused}}
    </style></head><body>
      <div class="wrap">
        <div class="title">{html.escape(title)}</div>
        <div class="ticker-wrap" id="wrap"><div class="ticker" id="ticker">{inner_html}</div></div>
      </div>
      <script>(function(){{
        try {{
          var wrap=document.getElementById('wrap'); var ticker=document.getElementById('ticker');
          function setDuration() {{
            var wrapW=wrap.clientWidth||1; var tickW=ticker.scrollWidth||wrapW;
            var secsPerScreen=Math.max(5, {int(ticker_speed)});
            var duration=secsPerScreen*(0.5*tickW/wrapW);
            duration=Math.max(duration,10);
            ticker.style.setProperty('--duration', duration.toFixed(1)+'s');
          }}
          setDuration();
          var to=null; window.addEventListener('resize',function(){{ if(to)clearTimeout(to); to=setTimeout(setDuration,150); }});
        }} catch(e) {{}}
      }})();</script>
    </body></html>"""
    st.components.v1.html(html_str, height=height, scrolling=False)

def _clip(txt:str, limit:int)->str:
    if not isinstance(txt,str): return ""
    return txt if len(txt)<=limit else txt[:limit]+"…"

def build_logos_map(df: pd.DataFrame):
    if df.empty: return {}
    tmp=df.copy()
    tmp["topic_norm"]=tmp["topic"].apply(_norm_topic_val)
    tmp=tmp.dropna(subset=["channel_title","channel_thumb"])
    tmp["published_at"]=pd.to_datetime(tmp["published_at"],errors="coerce")
    tmp=(tmp.sort_values(["topic_norm","channel_title","published_at"],ascending=[True,True,False]).drop_duplicates(subset=["topic_norm","channel_title"]))
    g=(tmp.groupby("topic_norm").apply(lambda g:list(zip(g["channel_thumb"].tolist(), g["channel_title"].tolist()))))
    return g.to_dict()

def build_stats_map(df: pd.DataFrame):
    if df.empty: return {}
    tmp=df.copy()
    tmp["topic_norm"]=tmp["topic"].apply(_norm_topic_val)
    tmp["published_at"]=pd.to_datetime(tmp["published_at"],errors="coerce")
    tmp["date_only"]=tmp["published_at"].dt.date
    for c in ["view_count","like_count","comment_count"]:
        if c not in tmp.columns: tmp[c]=0
        tmp[c]=pd.to_numeric(tmp[c], errors="coerce").fillna(0)
    agg=(tmp.groupby("topic_norm").agg(channels=("channel_title",lambda s:s.dropna().nunique()),days=("date_only",lambda s:s.dropna().nunique()),views=("view_count","sum"),likes=("like_count","sum"),comments=("comment_count","sum")).reset_index())
    out={}
    for _,r in agg.iterrows():
        out[r["topic_norm"]]={"channels":int(r["channels"] or 0),"days":int(r["days"] or 0),"views":int(r["views"] or 0),"likes":int(r["likes"] or 0),"comments":int(r["comments"] or 0),"shares":0}
    return out

def logos_inline_html(logos:list, max_n:int=10):
    if not logos: return ""
    seen=set()
    items=[]
    for thumb,name in logos:
        if not thumb or thumb in seen: continue
        seen.add(thumb)
        items.append(f'<img src="{html.escape(str(thumb))}" referrerpolicy="no-referrer" title="{html.escape(str(name or ""))}" alt="{html.escape(str(name or ""))}" style="width:28px;height:28px;border-radius:50%;object-fit:cover;border:1px solid rgba(255,255,255,0.25);margin-left:8px">')
        if len(items)>=max_n: break
    return "".join(items)

def _demp_percent(stats:dict)->str:
    v=max(0,int(stats.get("views",0)))
    l=max(0,int(stats.get("likes",0)))
    c=max(0,int(stats.get("comments",0)))
    s=max(0,int(stats.get("shares",0) or 0))
    denom=max(1.0, math.log10(v + 10.0))
    score=((l*1.2 + c*1.5 + s*1.2) / (v/10) * 100.0)
    score=max(0.0, min(score, 99.9))
    return f"{score:.1f}%"

RENAME_CAMEL={"video_id":"videoId","channel_id":"channelId","channel_title":"channelTitle","channel_origin":"channelOrigin","channel_thumb":"channelThumb","channel_subscribers":"channelSubscribers","channel_total_views":"channelTotalViews","published_at":"publishedAt","duration_hms":"duration_hms","view_count":"viewCount","like_count":"likeCount","comment_count":"commentCount","privacy_status":"privacyStatus","made_for_kids":"madeForKids","has_captions":"hasCaptions","url":"url","thumbnail":"thumbnail","title":"title","description":"description"}

def _row_to_card_shape(row:dict)->dict:
    out=dict(row)
    for k,v in list(row.items()):
        if k in RENAME_CAMEL: out[RENAME_CAMEL[k]]=v
    for k in ["title","url","thumbnail","channelTitle","channelThumb","channelUrl","description","channelSubscribers","channelTotalViews","channelOrigin","viewCount","likeCount","commentCount","duration_hms","publishedAt","hasCaptions"]:
        out.setdefault(k,"")
    return out

def card_markdown_pro(row:dict, idx:int)->str:
    r=_row_to_card_shape(row)
    title=r.get("title",""); url=r.get("url",""); thumb=r.get("thumbnail",""); ch=r.get("channelTitle",""); chlogo=r.get("channelThumb","")
    subs=_fmt_count(r.get("channelSubscribers")); chviews=_fmt_count(r.get("channelTotalViews")); country=r.get("channelOrigin","") or "—"
    views=_fmt_count(r.get("viewCount")); likes=_fmt_count(r.get("likeCount")); comments=_fmt_count(r.get("commentCount"))
    desc_raw=(r.get("description","") or "").replace("\n"," "); desc=desc_raw[:450]+("…" if len(desc_raw)>450 else "")
    dur=r.get("duration_hms") or "—"; pub=r.get("publishedAt") or "—"; cap="No" if not r.get("hasCaptions") else "Yes"
    img_tag = f'<img src="{chlogo}" referrerpolicy="no-referrer" style="width:22px;height:22px;border-radius:50%;object-fit:cover" />' if chlogo else ""
    ch_head = "<div style='display:flex;align-items:center;gap:8px;'>"+f"{img_tag}<span style='font-weight:600;color:#ffffff;'>{html.escape(str(ch))}</span></div>"
    title_link = f'<a href="{url}" target="_blank" style="text-decoration:none;color:{THEME["link"]};">{html.escape(str(title))}</a>' if url else html.escape(str(title))
    return f"""<div style="display:flex;gap:8px;margin:10px 0;">
  <div style="width:26px;text-align:center;font-weight:700;font-size:16px;color:{THEME['muted']};">{idx}</div>
  <div style="flex:1;border:1px solid {THEME['border']};border-radius:12px;padding:10px;box-shadow:0 3px 10px rgba(2,6,23,.25);background:{THEME['card']}">
    <div style="font-size:1.08rem;font-weight:700;margin:2px 0 10px 0;color:{THEME['ink']}">{title_link}</div>
    <div style="display:grid;grid-template-columns:230px 1fr 300px;gap:12px;align-items:start;">
      <div>{f'<a href="{url}" target="_blank"><img src="{thumb}" referrerpolicy="no-referrer" style="width:100%;height:auto;border-radius:10px"></a>' if thumb else ''}</div>
      <div>
        <div style="display:flex;gap:24px;font-weight:600;margin-bottom:6px;color:{THEME['ink']}">
          <div>Views: {views}</div><div>Comments: {comments}</div><div>Likes: {likes}</div><div>⏱ {dur} • {pub}</div><div>Captions: {cap}</div>
        </div>
        <div style="color:{THEME['ink']};line-height:1.35;"><span style="font-weight:700;color:{THEME['desc_label']};">Description:</span> {html.escape(desc)}</div>
      </div>
      <div style="border-left:2px dotted #33507a;padding-left:12px">{ch_head}
        <div style="margin-top:6px;color:{THEME['ink']}">
          <div>Subscribers: {subs}</div><div>Views: {chviews}</div><div>Country: {html.escape(str(country))}</div>
        </div>
      </div>
    </div>
  </div>
</div>"""

try:
    from langdetect import detect as _lang_detect
except Exception:
    _lang_detect = None
_ARABIC_URDU_REGEX = re.compile(r'[\u0600-\u06FF]')
def is_english_title(text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    t = text.strip()
    if _lang_detect is not None:
        try:
            return _lang_detect(t) == "en"
        except Exception:
            pass
    if _ARABIC_URDU_REGEX.search(t):
        return False
    letters = re.findall(r'[A-Za-z]', t)
    ratio = len(letters) / max(1, len(t))
    return ratio >= 0.50

engine = create_engine("postgresql://neondb_owner:npg_dK3TSAthwBV9@ep-orange-pine-a4qmdhiq-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
videos = pd.read_sql("SELECT * FROM videos;", engine)
if "title" in videos.columns: videos["title"] = videos["title"].apply(normalize_text)
allow = pd.read_sql("SELECT * FROM channels_allowlist;", engine)
search_videos = pd.read_sql("SELECT * FROM search_videos;", engine)
results = pd.read_sql("SELECT * FROM ai_results;", engine)

total_df = pd.merge(results, search_videos, how="inner", left_on="topic", right_on="matched_term")
total_df_final = pd.merge(total_df, videos, how="inner", left_on="video_id", right_on="video_id")
if "created_at" in total_df_final.columns:
    total_df_final["created_at"]=pd.to_datetime(total_df_final["created_at"], errors="coerce")
if "published_at" in total_df_final.columns:
    total_df_final["published_at"]=pd.to_datetime(total_df_final["published_at"], errors="coerce")

results_local = results[results["topic"].str.contains("Pakistan", case=False, na=False)]
_results_local = results_local.copy()
_search_videos = search_videos.copy()

_results_local["topic_key"] = _norm_key(_results_local["topic"])
_search_videos["matched_term_key"] = _norm_key(_search_videos["matched_term"])

results_local_1 = (
    _results_local
    .merge(
        _search_videos[["matched_term_key", "video_id", "search_run_id"]],
        left_on="topic_key",
        right_on="matched_term_key",
        how="inner"
    )
    .loc[:, ["topic", "video_id", "search_run_id"]]
    .drop_duplicates()
)

results_local_final = (
    results_local_1
    .merge(videos, on="video_id", how="left")
    # filter: only keep videos whose title also contains 'Pakistan'
    .query("title.str.contains('Pakistan', case=False, na=False)", engine="python")
    .loc[:, ["topic", "video_id", "search_run_id"] + [c for c in videos.columns if c != "video_id"]]
    .sort_values(by="published_at", ascending=False)
    .drop_duplicates(subset="video_id", keep="first")
)


results_int = results[~results["topic"].str.contains("Pakistan", case=False, na=False)].copy()
_results_int = results_int.copy()
_search_videos_int = search_videos.copy()
_results_int["topic_key"]=_norm_key(_results_int["topic"])
_search_videos_int["matched_term_key"]=_norm_key(_search_videos_int["matched_term"])
results_int_1 = (_results_int.merge(_search_videos_int[['matched_term_key','video_id','search_run_id']],left_on='topic_key', right_on='matched_term_key', how='inner').loc[:, ['topic','video_id','search_run_id']].drop_duplicates())
results_int_final = (results_int_1.merge(videos, on="video_id", how="left").loc[:, ['topic','video_id','search_run_id'] + [c for c in videos.columns if c != 'video_id']].sort_values(by='published_at', ascending=False).drop_duplicates(subset='video_id', keep='first'))
results_int_final["channel_url_norm"] = _norm_url(results_int_final.get("channel_url",""))
allow["channel_url_norm"] = _norm_url(allow.get("channel_url",""))
filtered_results_int = results_int_final[results_int_final["channel_url_norm"].isin(allow["channel_url_norm"])]
if "channel_origin" in filtered_results_int.columns:
    filtered_results_int = filtered_results_int[filtered_results_int["channel_origin"] != "Pakistan"]

logos_map_all  = build_logos_map(total_df_final)
stats_map_all  = build_stats_map(total_df_final)

_videos_channels = videos.copy()
_videos_channels["channel_url_norm"] = _norm_url(_videos_channels.get("channel_url", ""))
if "published_at" in _videos_channels.columns:
    _videos_channels["published_at"] = pd.to_datetime(_videos_channels["published_at"], errors="coerce")
    _videos_channels = (_videos_channels.sort_values("published_at", ascending=False).drop_duplicates(subset=["channel_url_norm"], keep="first"))
else:
    _videos_channels = _videos_channels.drop_duplicates(subset=["channel_url_norm"], keep="first")
allow["channel_url_norm"] = _norm_url(allow.get("channel_url", ""))
_not_allowed = _videos_channels[~_videos_channels["channel_url_norm"].isin(allow["channel_url_norm"])]
_not_allowed["__pick_label__"] = _not_allowed.apply(lambda r: f"{str(r.get('channel_title','') or '').strip()}",axis=1)

params = st.query_params
view   = (params.get("view") or "").strip().lower()
topic_q= params.get("topic")

def report_card_html_pro(row:dict, idx:int, logos:list, stats:dict, is_local:bool)->str:
    topic=row.get("topic","") or ""
    date_val=row.get("created_at","")
    date_str=date_val.strftime("%Y-%m-%d %H:%M") if isinstance(date_val, pd.Timestamp) else str(date_val or "")
    hashtags=row.get("ai_hashtags","") or ""
    insights=_clip(row.get("ai_insights","") or "", 380)
    summary=_clip(row.get("ai_summary","") or "", 420)
    title_url="?view=report&topic="+urllib.parse.quote_plus(topic)
    ch=_fmt_num((stats or {}).get("channels",0)); dy=_fmt_num((stats or {}).get("days",0))
    vw=_fmt_num((stats or {}).get("views",0)); lk=_fmt_num((stats or {}).get("likes",0)); cm=_fmt_num((stats or {}).get("comments",0)); sh="—"
    demp=_demp_percent(stats or {})
    logos_right=logos_inline_html(logos, max_n=10)
    return f"""
    <div style="display:flex;gap:10px;margin:14px 0;">
      <div style="width:26px;text-align:center;font-weight:700;font-size:16px;color:{THEME['muted']};">{idx}</div>
      <div style="flex:1;background:{THEME['card']};border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:18px;position:relative;box-shadow:0 3px 10px rgba(2,6,23,.25)">
        <div style="position:absolute;top:12px;right:14px;display:flex;align-items:center;">{logos_right}</div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <a href="{title_url}" style="color:{THEME['link']};font-weight:800;font-size:1.05rem;text-decoration:none">{html.escape(topic)}</a>
        </div>
        <div style="color:{THEME['ink']};font-weight:600;margin-bottom:6px;">
            Channels: {ch} • Days: {dy} • Views: {vw} • Likes: {lk} • Comments: {cm} • Shares: {sh} • <span style="color:#ff4d4d;font-weight:800"> Traction Index: {demp}</span>
        </div>
        <div style="color:{THEME['muted']};font-weight:600;margin-bottom:4px;">Date: {html.escape(date_str)} &nbsp;&nbsp; Hashtags: {html.escape(hashtags)}</div>
        <div style="margin-top:8px;">
          <div style="color:{THEME['desc']};font-weight:800;margin-bottom:4px;">AI Insights</div>
          <div style="color:{THEME['ink']};margin-bottom:10px;">{html.escape(insights)}</div>
          <div style="color:{THEME['desc']};font-weight:800;margin-bottom:4px;">Summary</div>
          <div style="color:{THEME['ink']};">{html.escape(summary)}</div>
        </div>
      </div>
    </div>
    """

def _pdf_build(topic, header_row, stats_dict, videos_df):
    import io, html, urllib.request
    import pandas as pd
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame,
        Paragraph, Spacer, Table, TableStyle, Image,
        NextPageTemplate, PageBreak
    )

    def _comma(v):
        try:
            n = int(float(v))
            return f"{n:,}"
        except Exception:
            return str(v or "0")

    def _hex(c):
        try:
            return colors.HexColor(c)
        except Exception:
            return colors.white

    def _fetch_image(url: str | None, w: float, h: float):
        if not url:
            return Spacer(w, h)
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = resp.read()
            img = Image(io.BytesIO(data), width=w, height=h)
            img.hAlign = "LEFT"
            return img
        except Exception:
            return Spacer(w, h)

    buf = io.BytesIO()

    # Margins
    lm = rm = 18 * mm
    tm = bm = 16 * mm

    # Frames
    L = landscape(A4)
    frame_portrait = Frame(lm, bm, A4[0] - lm - rm, A4[1] - tm - bm, id="portrait")
    frame_land     = Frame(lm, bm, L[0]  - lm - rm, L[1]  - tm - bm, id="landscape")

    # Background color for all pages
    page_bg_hex = (header_row or {}).get("page_bg_hex") or (PDF_COLORS.get("card", "#f1f5f9") if "PDF_COLORS" in globals() else "#f1f5f9")
    page_bg = _hex(page_bg_hex)

    def _draw_bg(c, pagesize):
        c.saveState()
        c.setFillColor(page_bg)
        c.setStrokeColor(page_bg)
        c.rect(0, 0, pagesize[0], pagesize[1], stroke=0, fill=1)
        c.restoreState()

    def _on_portrait(c, d):
        _draw_bg(c, A4); c.setPageSize(A4)

    def _on_land(c, d):
        _draw_bg(c, L); c.setPageSize(L)

    doc = BaseDocTemplate(buf, leftMargin=lm, rightMargin=rm, topMargin=tm, bottomMargin=bm, pagesize=A4)
    doc.addPageTemplates([
        PageTemplate(id="Portrait",  frames=[frame_portrait], onPage=_on_portrait),
        PageTemplate(id="Landscape", frames=[frame_land],     onPage=_on_land),
    ])

    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("h_title", parent=styles["Heading1"], fontName="Helvetica-Bold",
                             fontSize=22, alignment=1, textColor=colors.black, spaceAfter=10)
    h_topic = ParagraphStyle("h_topic", parent=styles["Heading2"], fontName="Helvetica-Bold",
                             fontSize=14, textColor=colors.black, spaceAfter=6)
    label = ParagraphStyle("label", parent=styles["Normal"], fontName="Helvetica",
                           fontSize=10.5, textColor=colors.black, leading=14)
    section = ParagraphStyle("section", parent=styles["Heading3"], fontName="Helvetica-Bold",
                             fontSize=12, textColor=colors.black, spaceAfter=4, spaceBefore=6)
    tag_style = ParagraphStyle("tags", parent=styles["Normal"], fontName="Helvetica",
                               fontSize=10.5, textColor=colors.black, leading=14)

    elems = []

    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    
    title = Paragraph("Central Monitoring Unit – Digital Media Report", h_title)
    logo = None
    if report_logo_url:
        try:
            logo = _fetch_image(report_logo_url)
        except Exception:
            logo = None
    
    if logo:
        header_table = Table(
            [[title, logo]],
            colWidths=[None, None],
            hAlign="LEFT"
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elems.append(header_table)
    else:
        elems.append(title)
    
    elems.append(Spacer(1, 6*mm))


    topic_text = f"Topic: {html.escape(str(topic))}"
    elems.append(Paragraph(topic_text, h_topic))

    created = (header_row or {}).get("created_at", "")
    try:
        created_str = created.strftime("%Y-%m-%d %H:%M")
    except Exception:
        created_str = str(created or "")
    elems.append(Paragraph(f"Date: {created_str}", label))
    elems.append(Spacer(1, 5 * mm))

    ai_insights = html.escape((header_row or {}).get("ai_insights", "") or "")
    summary     = html.escape((header_row or {}).get("ai_summary", "") or "")
    hashtags    = html.escape((header_row or {}).get("ai_hashtags", "") or "")

    elems.append(Paragraph("AI Insights", section))
    elems.append(Paragraph(ai_insights, label))
    elems.append(Spacer(1, 4 * mm))

    elems.append(Paragraph("Summary", section))
    elems.append(Paragraph(summary, label))
    elems.append(Spacer(1, 4 * mm))

    if hashtags:
        elems.append(Paragraph("Hashtags", section))
        elems.append(Paragraph(hashtags, tag_style))

    # Switch to landscape for table
    elems.append(NextPageTemplate("Landscape"))
    elems.append(PageBreak())

    table_title = ParagraphStyle("table_title", parent=styles["Heading2"], fontName="Helvetica-Bold",
                                 fontSize=14, textColor=colors.black, spaceAfter=6)
    elems.append(Paragraph("Relevant Videos", table_title))
    elems.append(Spacer(1, 2 * mm))

    # Usable width
    avail_w = L[0] - lm - rm

    # Columns: Thumb, Logo, Title, Channel, Views, Likes, Comments, Published, URL
    ratios = [0.10, 0.07, 0.24, 0.14, 0.06, 0.06, 0.07, 0.10, 0.16]
    col_widths = [r * avail_w for r in ratios]

    # Colors
    ink = (PDF_COLORS.get("ink", "#0e1629") if "PDF_COLORS" in globals() else "#0e1629")
    band = (PDF_COLORS.get("band", "#0e1629") if "PDF_COLORS" in globals() else "#0e1629")
    band_text = (PDF_COLORS.get("band_text", "#ffffff") if "PDF_COLORS" in globals() else "#ffffff")
    card = (PDF_COLORS.get("card", "#f1f5f9") if "PDF_COLORS" in globals() else "#f1f5f9")
    card_alt = (PDF_COLORS.get("card_alt", "#e2e8f0") if "PDF_COLORS" in globals() else "#e2e8f0")
    border = (PDF_COLORS.get("border", "#cbd5e1") if "PDF_COLORS" in globals() else "#cbd5e1")

    cell = ParagraphStyle("cell", parent=styles["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=12, textColor=_hex(ink), wordWrap="CJK")
    header_style = ParagraphStyle("hdr", parent=styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=10, textColor=colors.white)

    # Header row
    rows = [[
        Paragraph("Thumb",     header_style),
        Paragraph("Logo",      header_style),
        Paragraph("Title",     header_style),
        Paragraph("Channel",   header_style),
        Paragraph("Views",     header_style),
        Paragraph("Likes",     header_style),
        Paragraph("Comments",  header_style),
        Paragraph("Published", header_style),
        Paragraph("URL",       header_style),
    ]]

    vids = videos_df.copy()
    # Normalize common variants
    ren = {}
    if "published_at" not in vids.columns and "publishedAt" in vids.columns:
        ren["publishedAt"] = "published_at"
    if "channel_title" not in vids.columns and "channelTitle" in vids.columns:
        ren["channelTitle"] = "channel_title"
    if "view_count" not in vids.columns and "viewCount" in vids.columns:
        ren["viewCount"] = "view_count"
    if "like_count" not in vids.columns and "likeCount" in vids.columns:
        ren["likeCount"] = "like_count"
    if "comment_count" not in vids.columns and "commentCount" in vids.columns:
        ren["commentCount"] = "comment_count"
    vids = vids.rename(columns=ren)

    vids["published_at"] = pd.to_datetime(vids.get("published_at"), errors="coerce")

    # Image sizes
    THUMB_W, THUMB_H = 28*mm, 16*mm
    LOGO_W,  LOGO_H  = 14*mm, 14*mm

    for r in vids.to_dict("records"):
        title_txt   = html.escape(str(r.get("title", "") or ""))
        channel_txt = html.escape(str(r.get("channel_title", "") or ""))

        pub = r.get("published_at")
        pub_str = pub.strftime("%Y-%m-%d %H:%M") if isinstance(pub, pd.Timestamp) and pd.notna(pub) else ""

        thumb_url = r.get("thumbnail") or r.get("thumbnails") or r.get("thumb")
        logo_url  = r.get("channel_thumb") or r.get("channelThumb") or r.get("channel_logo")

        thumb_img = _fetch_image(thumb_url, THUMB_W, THUMB_H)
        logo_img  = _fetch_image(logo_url,  LOGO_W,  LOGO_H)

        rows.append([
            thumb_img,
            logo_img,
            Paragraph(title_txt, cell),
            Paragraph(channel_txt, cell),
            _comma(r.get("view_count")),
            _comma(r.get("like_count")),
            _comma(r.get("comment_count")),
            pub_str,
            Paragraph(html.escape(str(r.get("url","") or "")), cell),
        ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _hex(band)),
        ("TEXTCOLOR",     (0, 0), (-1, 0), _hex(band_text)),
        ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
        ("ALIGN",         (4, 1), (6, -1), "RIGHT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_hex(card), _hex(card_alt)]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), _hex(ink)),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, _hex(border)),
        ("BOX",           (0, 0), (-1, -1), 0.25, _hex(border)),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elems.append(tbl)
    doc.build(elems)
    buf.seek(0)
    return buf




def render_detail_page(topic: str):
    st.markdown("<a href='?' style='text-decoration:none'>&larr; Back to dashboard</a>", unsafe_allow_html=True)
    norm=_norm_topic_val(topic)
    is_local = ("pakistan" in norm) or ("پاکستان" in topic)
    logos = logos_map_all.get(norm, [])
    stats = stats_map_all.get(norm, {})
    rep_row = (total_df_final[total_df_final["topic"].apply(lambda x:_norm_topic_val(str(x))==norm)]
               .sort_values("created_at", ascending=False)
               .head(1)
               .to_dict("records"))
    header = rep_row[0] if rep_row else {"topic":topic,"ai_insights":"","ai_summary":"","ai_hashtags":"","created_at":""}
    st.markdown("## AI Reports")
    st.markdown(report_card_html_pro(header, 1, logos, stats, is_local), unsafe_allow_html=True)
    show = total_df_final[total_df_final["topic"].apply(lambda x:_norm_topic_val(str(x))==norm)].copy()
    if show.empty:
        st.info("No videos found for this topic.")
        return
    show["__is_english__"] = show["title"].apply(is_english_title)
    show = show[show["__is_english__"] == True]
    if is_local:
        show = show[show["title"].str.contains(r"\bpakistan\b", case=False, na=False) | show["title"].str.contains("پاکستان", case=False, na=False)]
    else:
        show["channel_url_norm"] = _norm_url(show.get("channel_url", ""))
        allow_set = set(allow["channel_url_norm"].tolist())
        show = show[show["channel_url_norm"].isin(allow_set)]
    show["published_at"] = pd.to_datetime(show["published_at"], errors="coerce")
    show["__title_key__"] = show["title"].apply(normalize_text)
    show = (show
            .sort_values(["published_at","video_id"], ascending=[False, True])
            .drop_duplicates(subset=["__title_key__","published_at"], keep="first")
            .drop(columns=["__title_key__","__is_english__","channel_url_norm"], errors="ignore"))
    st.markdown("### Videos")
    if show.empty:
        st.info("No videos match the filters for this topic.")
    else:
        for i,row in enumerate(show.to_dict("records"), start=1):
            st.markdown(card_markdown_pro(row, i), unsafe_allow_html=True)
    header["report_logo_url"] = "https://raw.githubusercontent.com/Rugger85/DEMP-FR/main/logo.jpeg"
    pdf_buf = _pdf_build(topic, header, stats, show)
    clicked = st.download_button(
        label="⬇️ Download PDF Report",
        data=pdf_buf,
        file_name=f"report_{_norm_topic_val(topic)[:60]}.pdf",
        mime="application/pdf",
        key=f"dl_btn_{_norm_topic_val(topic)}"
    )
    if "reports_downloaded" not in st.session_state:
        st.session_state["reports_downloaded"] = 0
    if clicked:
        st.session_state["reports_downloaded"] += 1

def _kpi_card_html(title:str, value:str)->str:
    return f"""
    <div style="background:{THEME['card']};border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:14px 16px;box-shadow:0 3px 10px rgba(2,6,23,.18);">
      <div style="color:{THEME['muted']};font-weight:700;margin-bottom:6px">{html.escape(title)}</div>
      <div style="color:{THEME['ink']};font-weight:900;font-size:1.6rem;letter-spacing:.4px">{html.escape(str(value))}</div>
    </div>
    """

if view=="report" and topic_q:
    render_detail_page(topic_q)
else:
    if "reports_downloaded" not in st.session_state:
        st.session_state["reports_downloaded"] = 0
    _v = videos.copy()
    _v["channel_url_norm"] = _norm_url(_v.get("channel_url", ""))
    if _v["channel_url_norm"].notna().any() and (_v["channel_url_norm"] != "").any():
        channels_in_videos = _v.loc[_v["channel_url_norm"] != "", "channel_url_norm"].nunique()
    elif "channel_id" in _v.columns:
        channels_in_videos = _v["channel_id"].dropna().nunique()
    else:
        channels_in_videos = _v["channel_title"].dropna().nunique()

    reports_generated = results.dropna(subset=["topic"]).assign(
        t=lambda d: d["topic"].apply(_norm_topic_val)
    )["t"].nunique()

    unique_video_titles = videos.dropna(subset=["title"]).assign(
        t=lambda d: d["title"].apply(normalize_text)
    ).query("t != ''")["t"].nunique()

    unique_channel_origins = (
        videos.get("channel_origin", pd.Series(dtype=str))
        .astype(str).str.strip().replace({"": pd.NA})
        .dropna().nunique()
    )

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.markdown(_kpi_card_html("Monitored Channels", _fmt_num(channels_in_videos)), unsafe_allow_html=True)
    with b2:
        st.markdown(_kpi_card_html("Reports Generated", _fmt_num(reports_generated)), unsafe_allow_html=True)
    with b3:
        st.markdown(_kpi_card_html("Videos Monitered", _fmt_num(unique_video_titles)), unsafe_allow_html=True)
    with b4:
        st.markdown(_kpi_card_html("Countries", _fmt_num(unique_channel_origins)), unsafe_allow_html=True)


    st.title("Recent Issues")
    with st.sidebar:
        ticker_speed = st.slider("Ticker speed (seconds per screen)", 10, 120, 80, 1)
        row_gap      = st.slider("Card gap (px)", 8, 48, 12, 1)
        seamless     = st.checkbox("Seamless scroll (duplicate content)", value=True)
        st.caption("Local ticker uses title+description filter containing 'Pakistan'. International ticker uses allow-list & non-Pakistan origin.")
        st.divider()
        st.subheader("Allow-list updater")
        options = _not_allowed["__pick_label__"].tolist()
        picked = st.multiselect("Add channels (not currently in allow-list)", options=options, help="Select channels to append into channels_allowlist")
        if picked:
            st.caption(f"Selected: {len(picked)} channel(s)")
        if st.button("➕ Append to allow-list"):
            if not picked:
                st.warning("Select one or more channels first.")
            else:
                rows_to_add = _not_allowed[_not_allowed["__pick_label__"].isin(picked)].copy()
                allow_schema_df = pd.read_sql("SELECT * FROM channels_allowlist LIMIT 0;", engine)
                db_cols = [c for c in allow_schema_df.columns if c.lower() != "id"]
                data_for_insert = {}
                for col in db_cols:
                    if col in rows_to_add.columns:
                        data_for_insert[col] = rows_to_add[col]
                    else:
                        if col == "channel_url" and "channel_url" in rows_to_add.columns:
                            data_for_insert[col] = rows_to_add["channel_url"]
                        elif col == "channel_title" and "channel_title" in rows_to_add.columns:
                            data_for_insert[col] = rows_to_add["channel_title"]
                        elif col == "channel_id" and "channel_id" in rows_to_add.columns:
                            data_for_insert[col] = rows_to_add["channel_id"]
                        elif col == "channel_thumb" and "channel_thumb" in rows_to_add.columns:
                            data_for_insert[col] = rows_to_add["channel_thumb"]
                        elif col == "country" and "channel_origin" in rows_to_add.columns:
                            data_for_insert[col] = rows_to_add["channel_origin"]
                        else:
                            data_for_insert[col] = pd.NA
                to_insert_df = pd.DataFrame(data_for_insert)
                if "channel_url" in to_insert_df.columns:
                    to_insert_df = to_insert_df.dropna(subset=["channel_url"]).drop_duplicates(subset=["channel_url"])
                if not to_insert_df.empty:
                    to_insert_df[db_cols].to_sql("channels_allowlist", con=engine, if_exists="append", index=False)
                    st.success(f"Appended {len(to_insert_df)} channel(s) to allow-list.")
                    allow = pd.read_sql("SELECT * FROM channels_allowlist;", engine)
                    allow["channel_url_norm"] = _norm_url(allow.get("channel_url", ""))
                    _not_allowed_mask = ~_videos_channels["channel_url_norm"].isin(allow["channel_url_norm"])
                    _not_allowed = _videos_channels[_not_allowed_mask].copy()
                    _not_allowed["__pick_label__"] = _not_allowed.apply(
                        lambda r: f"{str(r.get('channel_title','') or '').strip()} — {str(r.get('channel_url','') or '').strip()}",
                        axis=1
                    )
                else:
                    st.info("Nothing to insert (duplicates or empty selection).")
        st.divider()
        st.subheader("Remove from allow-list")
        allow_options = allow.apply(lambda r: f"{r.get('channel_title','') or ''} — {r.get('channel_url','') or ''}", axis=1).tolist()
        remove_choice = st.selectbox("Select channel to remove", options=[""] + allow_options, index=0, help="Pick a channel from the current allow-list to delete")
        if st.button("🗑 Remove from allow-list"):
            if not remove_choice or remove_choice.strip() == "":
                st.warning("Please select a channel first.")
            else:
                url_part = remove_choice.split("—")[-1].strip()
                try:
                    with engine.begin() as conn:
                        conn.execute(_sql_text("DELETE FROM channels_allowlist WHERE channel_url = :url"), {"url": url_part})
                    st.success(f"Removed: {remove_choice}")
                    allow = pd.read_sql("SELECT * FROM channels_allowlist;", engine)
                    allow["channel_url_norm"] = _norm_url(allow.get("channel_url", ""))
                    _not_allowed_mask = ~_videos_channels["channel_url_norm"].isin(allow["channel_url_norm"])
                    _not_allowed = _videos_channels[_not_allowed_mask].copy()
                    _not_allowed["__pick_label__"] = _not_allowed.apply(
                        lambda r: f"{str(r.get('channel_title','') or '').strip()} — {str(r.get('channel_url','') or '').strip()}",
                        axis=1
                    )
                except Exception as e:
                    st.error(f"Error removing channel: {e}")
    a1, a2 = st.columns([7,5])  # give map more room

    with a1:
        ticker_rows_local = results_local_final.copy()
        for c in ["title","channel_title","channel_thumb","url","published_at","video_id"]:
            if c not in ticker_rows_local.columns: ticker_rows_local[c] = ""
        ticker_rows_local["__en__"] = ticker_rows_local["title"].fillna("").apply(is_english_title)
        ticker_rows_local = ticker_rows_local[ticker_rows_local["__en__"] == True]
        ticker_rows_local["__title_key__"] = ticker_rows_local["title"].fillna("").apply(normalize_text)
        ticker_rows_local["published_at"] = pd.to_datetime(ticker_rows_local["published_at"], errors="coerce")
        ticker_rows_local = (
            ticker_rows_local
            .sort_values(["published_at","video_id"], ascending=[False, True])
            .drop_duplicates(subset=["__title_key__","published_at"], keep="first")
            .drop(columns=["__en__","__title_key__"], errors="ignore")
        )
        st.markdown("Pakistan's Issues")
        render_title_ticker(
            ticker_rows_local,
            title="",
            ticker_speed=max(6, int(ticker_speed * 0.8)),  # slightly faster for a smaller box
            row_gap=max(6, int(row_gap * 0.6)),            # tighter gap to shrink overall block
            seamless_scroll=seamless,
            height=100                                     # ↓ main knob to shrink the ticker box
        )

        ticker_rows_int = filtered_results_int.copy()
        for c in ["title","channel_title","channel_thumb","url","published_at","video_id"]:
            if c not in ticker_rows_int.columns: ticker_rows_int[c] = ""
        ticker_rows_int["__en__"] = ticker_rows_int["title"].fillna("").apply(is_english_title)
        ticker_rows_int = ticker_rows_int[ticker_rows_int["__en__"] == True]
        ticker_rows_int["__title_key__"] = ticker_rows_int["title"].fillna("").apply(normalize_text)
        ticker_rows_int["published_at"] = pd.to_datetime(ticker_rows_int["published_at"], errors="coerce")
        ticker_rows_int = (
            ticker_rows_int
            .sort_values(["published_at","video_id"], ascending=[False, True])
            .drop_duplicates(subset=["__title_key__","published_at"], keep="first")
            .drop(columns=["__en__","__title_key__"], errors="ignore")
        )
        st.markdown("International")
        render_title_ticker(
            ticker_rows_int,
            title="",
            ticker_speed=max(6, int(ticker_speed * 0.8)),
            row_gap=max(6, int(row_gap * 0.6)),
            seamless_scroll=seamless,
            height=100                                     # match the smaller height
        )

    with a2:
        country_counts = (
            videos["channel_origin"]
            .astype(str)
            .str.strip()
            .replace({"": pd.NA, "nan": pd.NA})
            .dropna()
            .value_counts()
            .rename_axis("Country")
            .reset_index(name="Videos")
        )

        if not country_counts.empty:
            fig = px.choropleth(
                country_counts,
                locations="Country",
                locationmode="country names",
                color="Videos",
                color_continuous_scale="Blues",
            )
            fig.update_geos(
                fitbounds="locations",    # zoom to the data
                visible=False             # hide frame/grids so the map fills tight
            )
            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font_color=THEME["ink"],
                coloraxis_showscale=False,
                height=420                # fixed height so it neatly fills the column
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(
                f"""
                <div style="background:{THEME['card']};border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:14px 16px;box-shadow:0 3px 10px rgba(2,6,23,.18);color:{THEME['muted']};font-weight:700;">
                Channel Origins Map — No countries found
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("## AI Reports")
    if total_df_final.empty:
        st.info("No reports available.")
    else:
        topics_latest = (
            total_df_final.sort_values("created_at", ascending=False)
            .dropna(subset=["topic"])
            .drop_duplicates(subset=["topic"], keep="first")
        )
        i = 1
        for r in topics_latest.to_dict("records"):
            t = r.get("topic","")
            is_local = is_pk_topic(t)
            norm = _norm_topic_val(t)
            logos = logos_map_all.get(norm, [])
            stats = stats_map_all.get(norm, {})
            st.markdown(report_card_html_pro(r, i, logos, stats, is_local), unsafe_allow_html=True)
            i += 1


    





















