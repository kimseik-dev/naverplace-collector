"""
네이버 플레이스 수집기 — 웹 대시보드 (Streamlit)

실행: streamlit run app.py
또는: run.command (Mac) / run.bat (Windows) 더블클릭
"""

import asyncio
import io
import threading
import queue
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.scraper import fetch_place_list, infer_category, to_dict_list
from src.exporter import COLUMN_ORDER, COLUMN_LABELS, COLUMN_WIDTHS


# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="네이버 플레이스 수집기",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 사이드바 (옵션) ─────────────────────────────────────────
st.sidebar.title("⚙️ 설정")

with st.sidebar:
    st.markdown("### 검색 옵션")
    limit = st.slider(
        "최대 수집 개수",
        min_value=10, max_value=100, value=60, step=10,
        help="네이버가 제공하는 한계까지만 수집됩니다 (대개 60개 내외)",
    )

    category_options = {
        "자동 추론 (추천)": None,
        "음식점 (restaurant)": "restaurant",
        "미용실 (hairshop)": "hairshop",
        "뷰티/네일/스파 (beautysalon)": "beautysalon",
        "병원 (hospital)": "hospital",
        "약국 (pharmacy)": "pharmacy",
        "카페 (cafe)": "cafe",
    }
    category_label = st.selectbox(
        "카테고리",
        options=list(category_options.keys()),
        index=0,
        help="키워드에서 자동 추론하거나 직접 지정",
    )
    category = category_options[category_label]

    enrich_phones = st.checkbox(
        "전화번호 자동 보강",
        value=True,
        help="목록 API에 전화가 없는 카테고리(미용실 등)는 상세 페이지에서 추가 수집. 느려지지만 정확함.",
    )

    st.markdown("---")
    st.markdown("### 안내")
    st.info(
        "⚠️ 학습/연구 목적으로만 사용하세요.\n\n"
        "네이버 이용약관과 robots.txt를 준수하고 "
        "과도한 요청은 자제해주세요."
    )


# ── 메인 화면 ──────────────────────────────────────────────
st.title("📍 네이버 플레이스 수집기")
st.caption("키워드로 네이버 플레이스 검색 결과를 수집해서 엑셀로 저장합니다.")

# 키워드 입력 + 시작 버튼
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "검색 키워드",
        value="강남맛집",
        placeholder="예: 강남맛집, 강남미용실, 강남역 카페...",
        label_visibility="collapsed",
    )
with col2:
    start_btn = st.button("🔍 수집 시작", type="primary", use_container_width=True)

# 카테고리 미리보기
if query:
    inferred = infer_category(query) if category is None else category
    st.caption(f"💡 적용 카테고리: **{inferred}**  |  목표 수집: 최대 **{limit}**개  |  "
               f"전화 보강: {'✅' if enrich_phones else '❌'}")


# ── 수집 로직 ──────────────────────────────────────────────
def run_scraper_in_thread(q: queue.Queue, kwargs: dict) -> None:
    """별도 스레드에서 asyncio.run() 호출. 결과/진행을 queue 로 전달."""
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
    """엑셀 파일을 메모리 버퍼에 만들어 다운로드용 bytes 반환."""
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


# ── 수집 실행 ──────────────────────────────────────────────
if start_btn:
    if not query.strip():
        st.error("키워드를 입력해주세요.")
    else:
        st.divider()
        status_box = st.empty()
        progress_bar = st.progress(0, text="준비 중...")
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

        # 진행 상황 폴링
        result = None
        error = None
        recent_msgs: list[str] = []
        start_ts = time.time()
        last_stage = "list"

        while worker.is_alive() or not q.empty():
            try:
                msg = q.get(timeout=0.3)
            except queue.Empty:
                # 경과 시간 표시 (idle 동안)
                elapsed = int(time.time() - start_ts)
                status_box.markdown(
                    f"⏳ **수집 진행 중...** (경과 {elapsed}초)"
                )
                continue

            kind = msg[0]
            if kind == "progress":
                _, stage, current, total, message = msg
                last_stage = stage
                pct = min(int(current / max(total, 1) * 100), 100)
                stage_label = {
                    "list": "📋 목록 수집",
                    "enrich": "📞 전화번호 보강",
                    "done": "✅ 완료",
                }.get(stage, stage)
                progress_bar.progress(pct / 100,
                                      text=f"{stage_label} — {current}/{total}")
                recent_msgs.append(f"`{datetime.now().strftime('%H:%M:%S')}` {message}")
                # 최근 8개만 표시
                log_box.markdown("\n\n".join(recent_msgs[-8:]))
            elif kind == "result":
                result = msg[1]
            elif kind == "error":
                error = msg[1]

        # ── 결과 표시 ──
        progress_bar.empty()
        status_box.empty()
        log_box.empty()

        if error:
            st.error(f"❌ 오류 발생: {error}")
        elif not result:
            st.warning("수집된 결과가 없습니다. 키워드/카테고리를 다시 확인해주세요.")
        else:
            df = build_dataframe(result)
            elapsed = int(time.time() - start_ts)

            # 요약 메트릭
            ad_count = int((df["광고여부"] == "광고").sum())
            normal = len(df) - ad_count
            phone_filled = (df["전화번호"].astype(str).str.strip() != "").sum()
            addr_filled = (df["주소"].astype(str).str.strip() != "").sum()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("총 수집", f"{len(df)}건")
            m2.metric("일반/광고", f"{normal} / {ad_count}")
            m3.metric("전화 수집", f"{phone_filled}/{len(df)}")
            m4.metric("주소 수집", f"{addr_filled}/{len(df)}")

            st.success(f"🎉 수집 완료 — 소요 시간 {elapsed}초")

            # 다운로드 버튼
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_q = query.replace("/", "_").replace(" ", "_")
            filename = f"naverplace_{safe_q}_{timestamp}.xlsx"
            xlsx_bytes = make_xlsx_bytes(df, query)
            st.download_button(
                "📥 엑셀 파일 다운로드",
                data=xlsx_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )

            # 결과 테이블
            st.markdown("### 📊 수집 결과")
            # 클릭 가능한 링크로 변환
            display_df = df.copy()
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "플레이스 URL": st.column_config.LinkColumn(
                        "플레이스 URL", display_text="🔗 열기"
                    ),
                    "순위": st.column_config.NumberColumn(width="small"),
                    "광고여부": st.column_config.TextColumn(width="small"),
                },
            )

# 첫 진입(수집 안 한 상태) 안내
else:
    st.markdown("""
    ### 사용 방법
    1. 좌측 사이드바에서 **수집 개수**(10~100)와 **카테고리**(자동 추천)를 설정
    2. 상단 입력창에 **검색 키워드** 입력 (예: 강남맛집, 강남미용실)
    3. **🔍 수집 시작** 버튼 클릭
    4. 진행 상황을 실시간으로 확인
    5. 완료되면 **📥 엑셀 다운로드** 버튼으로 결과 저장

    ### 수집되는 항목
    `순위` `업체명` `카테고리` `주소` `전화번호` `방문자리뷰` `블로그리뷰` `플레이스 URL` `플레이스 ID` `광고여부`

    ### 주의사항
    - 네이버 플레이스가 키워드별로 노출하는 결과 수에 제한이 있습니다 (대개 **약 60건** 내외)
    - 학습/연구 목적으로만 사용해주세요
    - 연속 실행 시 일시적으로 차단될 수 있습니다 → 1~2분 대기 후 재시도
    """)
