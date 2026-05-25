"""
네이버 플레이스 수집기 — 웹 대시보드 (Streamlit)

실행: streamlit run app.py
또는: run_mac.command (Mac) / run_windows.bat (Windows) 더블클릭
"""

import asyncio
import io
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.scraper import fetch_place_list, infer_category, to_dict_list
from src.exporter import COLUMN_ORDER, COLUMN_LABELS, COLUMN_WIDTHS


# ═══════════════════════════════════════════════════════════
#  페이지 설정
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="네이버 플레이스 수집기",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════
#  커스텀 CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* 한글 폰트 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;
}

/* 메인 헤더 영역 */
.hero {
    background: linear-gradient(135deg, #03C75A 0%, #00B050 100%);
    color: white;
    padding: 1.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 16px rgba(3,199,90,0.15);
}
.hero h1 { margin: 0; font-size: 1.7rem; font-weight: 700; }
.hero p  { margin: 0.4rem 0 0; opacity: 0.92; font-size: 0.95rem; }

/* 칩 (빠른 검색) */
.chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0 1rem; }
.chip {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    background: #F0F4FF;
    border: 1px solid #D6E2FF;
    border-radius: 999px;
    font-size: 0.85rem;
    color: #2540B8;
    cursor: pointer;
}

/* 메트릭 카드 */
[data-testid="stMetric"] {
    background: #FAFAFC;
    border: 1px solid #ECEEF1;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricLabel"] { color: #6B7280 !important; font-size: 0.8rem !important; }
[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; }

/* 결과 안내 박스 */
.info-box {
    background: #FFF9DB;
    border-left: 4px solid #FFD43B;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
    font-size: 0.9rem;
}

/* 광고 행 배경 */
.ad-row { background-color: #FFF4E6 !important; }

/* 사이드바 폰트 */
section[data-testid="stSidebar"] { font-size: 0.92rem; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
#  세션 상태 초기화
# ═══════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "history": [],          # 최근 검색 기록 (최대 10개)
        "last_results": None,   # 마지막 수집 결과
        "last_query": "",
        "last_category": "",
        "last_elapsed": 0,
        "search_running": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════
#  사이드바
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ 설정")

    limit = st.slider(
        "최대 수집 개수",
        min_value=10, max_value=100, value=60, step=10,
        help="네이버가 제공하는 한계까지만 수집됩니다 (대개 60개 내외)",
    )

    category_options = {
        "🤖 자동 추론 (추천)": None,
        "🍽 음식점": "restaurant",
        "💇 미용실": "hairshop",
        "💅 뷰티/네일/스파": "beautysalon",
        "🏥 병원": "hospital",
        "💊 약국": "pharmacy",
        "☕ 카페": "cafe",
    }
    category_label = st.selectbox(
        "카테고리",
        options=list(category_options.keys()),
        index=0,
        help="키워드에서 자동으로 추론하거나 직접 지정",
    )
    category = category_options[category_label]

    enrich_phones = st.toggle(
        "📞 전화번호 자동 보강",
        value=True,
        help="목록 API에 전화가 없는 카테고리(미용실 등)는 상세 페이지에서 추가 수집합니다. "
             "느려지지만 정확합니다.",
    )

    st.divider()

    # 최근 검색 기록
    st.markdown("### 🕘 최근 검색")
    if st.session_state.history:
        for h in reversed(st.session_state.history[-5:]):
            count = h.get('count', '?')
            q = h['query']
            cat = h.get('category', '')
            if st.button(f"🔍 {q} ({count}건)",
                         key=f"history_{h['ts']}",
                         use_container_width=True,
                         help=f"카테고리: {cat}"):
                st.session_state.last_results = h["results"]
                st.session_state.last_query = q
                st.session_state.last_category = cat
                st.session_state.last_elapsed = h.get('elapsed', 0)
                st.rerun()
    else:
        st.caption("아직 검색 기록이 없습니다")

    st.divider()
    with st.expander("ℹ️ 사용 안내"):
        st.caption(
            "**학습/연구 목적 전용** 도구입니다. "
            "네이버 이용약관과 robots.txt 를 준수하고 "
            "과도한 요청은 자제해주세요.\n\n"
            "키워드별로 네이버가 제공하는 최대 결과 수에 제한이 있어 "
            "대개 약 60건까지 수집됩니다."
        )


# ═══════════════════════════════════════════════════════════
#  메인 화면 — 헤더
# ═══════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
    <h1>📍 네이버 플레이스 수집기</h1>
    <p>키워드 한 번으로 업체명·주소·전화번호·리뷰수까지 한 번에 — 엑셀로 저장</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
#  검색 폼 (Enter 키 지원)
# ═══════════════════════════════════════════════════════════
QUICK_KEYWORDS = ["강남맛집", "강남미용실", "역삼카페", "신사 헤어샵", "압구정 맛집", "삼성동 점심"]

# 빠른 선택 칩
clicked_chip = None
chip_cols = st.columns(len(QUICK_KEYWORDS))
for i, kw in enumerate(QUICK_KEYWORDS):
    if chip_cols[i].button(kw, key=f"chip_{i}", use_container_width=True):
        clicked_chip = kw

with st.form("search_form", clear_on_submit=False):
    col1, col2 = st.columns([4, 1])
    with col1:
        default_query = clicked_chip if clicked_chip else st.session_state.get("last_query", "강남맛집")
        query = st.text_input(
            "검색 키워드",
            value=default_query,
            placeholder="예: 강남맛집, 강남미용실, 역삼카페...",
            label_visibility="collapsed",
        )
    with col2:
        start_btn = st.form_submit_button(
            "🔍 수집 시작",
            type="primary",
            use_container_width=True,
        )

# 입력 미리보기
if query:
    inferred = infer_category(query) if category is None else category
    phone_text = "✅ 활성" if enrich_phones else "⏭ 생략"
    st.caption(
        f"🎯 카테고리: **{inferred}**   ·   "
        f"📊 최대: **{limit}**개   ·   "
        f"📞 전화 보강: **{phone_text}**"
    )


# ═══════════════════════════════════════════════════════════
#  수집 로직 (스레드 + 큐로 진행 상황 전달)
# ═══════════════════════════════════════════════════════════
def run_scraper_in_thread(q: queue.Queue, kwargs: dict) -> None:
    def progress_cb(stage, current, total, message):
        q.put(("progress", stage, current, total, message))
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        kwargs["progress"] = progress_cb
        result = loop.run_until_complete(fetch_place_list(**kwargs))
        loop.close()
        q.put(("result", result))
    except Exception as e:
        q.put(("error", str(e)))


def build_dataframe(places) -> pd.DataFrame:
    rows = to_dict_list(places)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)[COLUMN_ORDER].rename(columns=COLUMN_LABELS)
    df["광고여부"] = df["광고여부"].map({True: "광고", False: ""})
    return df


def make_xlsx_bytes(df: pd.DataFrame, query: str) -> bytes:
    buf = io.BytesIO()
    sheet_name = (query or "결과")[:30]
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for col_idx, col_name in enumerate(df.columns, start=1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
                COLUMN_WIDTHS.get(col_name, 15)
            )
    buf.seek(0)
    return buf.getvalue()


def make_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# ═══════════════════════════════════════════════════════════
#  수집 실행
# ═══════════════════════════════════════════════════════════
if start_btn:
    if not query.strip():
        st.error("⚠️ 키워드를 입력해주세요.")
    else:
        st.divider()
        with st.container(border=True):
            status_box = st.empty()
            progress_bar = st.progress(0, text="🚀 준비 중...")
            log_box = st.empty()

            q: queue.Queue = queue.Queue()
            worker = threading.Thread(
                target=run_scraper_in_thread,
                args=(q, {
                    "query": query.strip(),
                    "limit": limit,
                    "headless": True,
                    "category": category,
                    "enrich_phones": enrich_phones,
                }),
                daemon=True,
            )
            worker.start()

            result = None
            error = None
            recent_msgs: list[str] = []
            start_ts = time.time()

            while worker.is_alive() or not q.empty():
                try:
                    msg = q.get(timeout=0.3)
                except queue.Empty:
                    elapsed = int(time.time() - start_ts)
                    status_box.markdown(
                        f"⏳ **수집 진행 중...** &nbsp;&nbsp;&nbsp; 경과 시간 **{elapsed}초**"
                    )
                    continue

                kind = msg[0]
                if kind == "progress":
                    _, stage, current, total, message = msg
                    pct = min(int(current / max(total, 1) * 100), 100)
                    stage_label = {
                        "list":   "📋 목록 수집",
                        "enrich": "📞 전화번호 보강",
                        "done":   "✅ 완료",
                    }.get(stage, stage)
                    progress_bar.progress(
                        pct / 100,
                        text=f"{stage_label}  ·  {current} / {total}  ({pct}%)",
                    )
                    recent_msgs.append(
                        f"`{datetime.now().strftime('%H:%M:%S')}` {message}"
                    )
                    log_box.markdown(
                        "\n\n".join(recent_msgs[-8:])
                    )
                elif kind == "result":
                    result = msg[1]
                elif kind == "error":
                    error = msg[1]

            progress_bar.empty()
            status_box.empty()
            log_box.empty()
            elapsed_total = int(time.time() - start_ts)

        if error:
            st.error(f"❌ 오류 발생: {error}")
            with st.expander("문제 해결 안내"):
                st.markdown("""
                - **차단된 경우**: 1~2분 대기 후 재시도
                - **셀렉터 변경**: `src/scraper.py` 의 `li.UEzoS, li.p0FrU` 부분 확인
                - **네트워크**: 인터넷 연결 확인
                """)
        elif not result:
            st.warning("⚠️ 수집된 결과가 없습니다. 키워드/카테고리를 다시 확인해주세요.")
        else:
            # 결과 저장 (세션) + 검색 기록 추가
            df = build_dataframe(result)
            st.session_state.last_results = result
            st.session_state.last_query = query
            st.session_state.last_category = infer_category(query) if category is None else category
            st.session_state.last_elapsed = elapsed_total
            st.session_state.history.append({
                "ts": time.time(),
                "query": query,
                "category": st.session_state.last_category,
                "count": len(df),
                "elapsed": elapsed_total,
                "results": result,
            })
            if len(st.session_state.history) > 10:
                st.session_state.history = st.session_state.history[-10:]
            st.rerun()


# ═══════════════════════════════════════════════════════════
#  결과 표시
# ═══════════════════════════════════════════════════════════
def render_results(result, q: str, cat: str, elapsed: int):
    df = build_dataframe(result)

    # 요약 메트릭
    ad_count = int((df["광고여부"] == "광고").sum())
    normal = len(df) - ad_count
    phone_filled = int((df["전화번호"].astype(str).str.strip() != "").sum())
    addr_filled = int((df["주소"].astype(str).str.strip() != "").sum())

    st.success(
        f"🎉 **{q}** 수집 완료 — 총 **{len(df)}건**  ·  소요 시간 **{elapsed}초**  ·  카테고리 **{cat}**"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 수집", f"{len(df)}건")
    m2.metric("일반 / 광고", f"{normal} / {ad_count}",
              help="광고는 사이트 노출 슬롯이며 일반 결과와 분리해 표시합니다")
    m3.metric("전화 수집", f"{phone_filled}/{len(df)}",
              delta=f"{int(phone_filled/len(df)*100)}%",
              delta_color="off")
    m4.metric("주소 수집", f"{addr_filled}/{len(df)}",
              delta=f"{int(addr_filled/len(df)*100)}%",
              delta_color="off")

    # 다운로드 (xlsx + csv 둘 다)
    st.markdown("### 📥 다운로드")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q = q.replace("/", "_").replace(" ", "_")
    d1, d2, _ = st.columns([1, 1, 2])
    with d1:
        st.download_button(
            "📊 엑셀 (.xlsx)",
            data=make_xlsx_bytes(df, q),
            file_name=f"naverplace_{safe_q}_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )
    with d2:
        st.download_button(
            "📄 CSV",
            data=make_csv_bytes(df),
            file_name=f"naverplace_{safe_q}_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── 탭으로 결과 분리 ──
    tab_all, tab_normal, tab_ad, tab_map, tab_stats = st.tabs([
        f"📋 전체 ({len(df)})",
        f"⭐ 일반 ({normal})",
        f"📢 광고 ({ad_count})",
        "🗺 지도",
        "📊 통계",
    ])

    # 컬럼 표시 설정 (공통)
    column_config = {
        "플레이스 URL": st.column_config.LinkColumn(
            "플레이스 URL", display_text="🔗 열기", width="small",
        ),
        "순위": st.column_config.NumberColumn(width="small"),
        "광고여부": st.column_config.TextColumn(width="small"),
        "전화번호": st.column_config.TextColumn(width="medium"),
        "방문자리뷰": st.column_config.NumberColumn(format="%s", width="small"),
        "블로그리뷰": st.column_config.NumberColumn(format="%s", width="small"),
        "위도": None,           # 테이블에서 숨김
        "경도": None,
        "플레이스 ID": None,
    }

    def _render_table(_df: pd.DataFrame, key_suffix: str):
        # 검색 + 정렬
        c1, c2 = st.columns([3, 1])
        with c1:
            search = st.text_input(
                "🔎 결과 안에서 검색 (업체명·주소)",
                key=f"search_{key_suffix}",
                label_visibility="collapsed",
                placeholder="🔎 업체명 또는 주소로 빠르게 찾기...",
            )
        with c2:
            sort_by = st.selectbox(
                "정렬",
                options=["순위(기본)", "방문자리뷰↓", "블로그리뷰↓", "업체명↑"],
                key=f"sort_{key_suffix}",
                label_visibility="collapsed",
            )

        view = _df.copy()
        if search:
            mask = (
                view["업체명"].astype(str).str.contains(search, case=False, na=False) |
                view["주소"].astype(str).str.contains(search, case=False, na=False)
            )
            view = view[mask]
        if sort_by == "방문자리뷰↓":
            view = view.copy()
            view["_v"] = view["방문자리뷰"].astype(str).str.replace(",", "", regex=False)
            view["_v"] = pd.to_numeric(view["_v"], errors="coerce").fillna(0)
            view = view.sort_values("_v", ascending=False).drop(columns=["_v"])
        elif sort_by == "블로그리뷰↓":
            view = view.copy()
            view["_b"] = view["블로그리뷰"].astype(str).str.replace(",", "", regex=False)
            view["_b"] = pd.to_numeric(view["_b"], errors="coerce").fillna(0)
            view = view.sort_values("_b", ascending=False).drop(columns=["_b"])
        elif sort_by == "업체명↑":
            view = view.sort_values("업체명")

        if view.empty:
            st.info("일치하는 결과가 없습니다.")
        else:
            st.caption(f"표시 중: {len(view)}건")
            st.dataframe(
                view,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
                height=min(600, (len(view) + 1) * 36),
            )

    with tab_all:
        _render_table(df, "all")

    with tab_normal:
        _render_table(df[df["광고여부"] != "광고"].reset_index(drop=True), "normal")

    with tab_ad:
        if ad_count == 0:
            st.info("이 키워드에는 광고 결과가 없습니다.")
        else:
            _render_table(df[df["광고여부"] == "광고"].reset_index(drop=True), "ad")

    with tab_map:
        # 좌표가 있는 행만 지도에 표시
        map_df = pd.DataFrame({
            "lat": [p.latitude for p in result if p.latitude],
            "lon": [p.longitude for p in result if p.longitude],
        })
        if map_df.empty:
            st.info("좌표 정보가 있는 업체가 없습니다.")
        else:
            st.caption(f"📍 지도에 {len(map_df)}개 업체 위치 표시")
            st.map(map_df, latitude="lat", longitude="lon", size=15, color="#FF4B4B")

    with tab_stats:
        # 카테고리 분포
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**카테고리 분포 (상위 10)**")
            cat_counts = df["카테고리"].replace("", "(미분류)").value_counts().head(10)
            st.bar_chart(cat_counts)
        with c2:
            st.markdown("**리뷰 수 상위 10**")
            top_reviews = df.copy()
            top_reviews["_r"] = pd.to_numeric(
                top_reviews["방문자리뷰"].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            ).fillna(0)
            top_reviews = top_reviews.nlargest(10, "_r")[["업체명", "방문자리뷰"]]
            st.dataframe(top_reviews, use_container_width=True, hide_index=True)

        st.markdown("**전화번호·주소 수집률**")
        st.progress(phone_filled / max(len(df), 1),
                    text=f"전화번호: {phone_filled}/{len(df)} ({int(phone_filled/max(len(df),1)*100)}%)")
        st.progress(addr_filled / max(len(df), 1),
                    text=f"주소: {addr_filled}/{len(df)} ({int(addr_filled/max(len(df),1)*100)}%)")


# 결과가 있으면 표시
if st.session_state.last_results:
    render_results(
        st.session_state.last_results,
        st.session_state.last_query,
        st.session_state.last_category,
        st.session_state.last_elapsed,
    )
elif not start_btn:
    # 빈 상태 — 사용 안내
    st.markdown("""
    ### 👋 시작하기

    **1단계** — 좌측에서 수집 개수와 카테고리를 설정합니다 (기본값 그대로도 OK)

    **2단계** — 상단의 빠른 선택 칩을 누르거나, 검색창에 키워드를 입력합니다

    **3단계** — 🔍 수집 시작 버튼을 누르면 진행 상황이 실시간으로 표시됩니다 (1~5분 소요)

    **4단계** — 완료되면 결과를 표·지도·통계로 확인하고 엑셀로 다운로드합니다
    """)

    with st.expander("📌 수집되는 항목 (열어보기)"):
        st.markdown("""
        - **순위** — 네이버 플레이스 노출 순서
        - **업체명** + **카테고리** — 상호명과 업종 분류
        - **주소** — 도로명 + 지번
        - **전화번호** — 대표 전화 또는 안심번호
        - **방문자 리뷰** / **블로그 리뷰** — 각 리뷰 수
        - **플레이스 URL** — 모바일 플레이스 페이지 직접 링크
        - **광고여부** — 광고 슬롯 여부
        - **좌표** — 지도 뷰용 위도·경도
        """)

    with st.expander("⚠️ 알아둘 점"):
        st.markdown("""
        - 네이버 플레이스는 키워드별로 노출 결과 수가 제한됩니다 (대개 약 **60건** 내외)
        - 너무 자주 연속 실행하면 일시적으로 차단될 수 있습니다 → 1~2분 대기 후 재시도
        - 학습/연구 목적으로만 사용해주세요
        """)
