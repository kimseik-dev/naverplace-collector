"""엑셀 출력 모듈."""

from pathlib import Path
from datetime import datetime

import pandas as pd


COLUMN_ORDER = [
    "rank", "name", "category", "address", "phone",
    "visitor_review", "blog_review", "place_url", "place_id", "is_ad",
]

COLUMN_LABELS = {
    "rank": "순위",
    "name": "업체명",
    "category": "카테고리",
    "address": "주소",
    "phone": "전화번호",
    "visitor_review": "방문자리뷰",
    "blog_review": "블로그리뷰",
    "place_url": "플레이스 URL",
    "place_id": "플레이스 ID",
    "is_ad": "광고여부",
}

COLUMN_WIDTHS = {
    "순위": 6, "업체명": 28, "카테고리": 16, "주소": 40,
    "전화번호": 16, "방문자리뷰": 10, "블로그리뷰": 10,
    "플레이스 URL": 45, "플레이스 ID": 14, "광고여부": 8,
}


def export_to_xlsx(rows: list[dict], query: str, out_dir: str = "output") -> Path:
    """수집 결과를 xlsx로 저장하고 파일 경로 반환."""
    if not rows:
        raise ValueError("저장할 데이터가 없습니다.")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query.replace("/", "_").replace(" ", "_")
    filename = out_path / f"naverplace_{safe_query}_{timestamp}.xlsx"

    df = pd.DataFrame(rows)[COLUMN_ORDER].rename(columns=COLUMN_LABELS)
    df["광고여부"] = df["광고여부"].map({True: "광고", False: ""})

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=query[:30] or "결과")
        ws = writer.sheets[query[:30] or "결과"]
        for col_idx, col_name in enumerate(df.columns, start=1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = (
                COLUMN_WIDTHS.get(col_name, 15)
            )

    return filename
