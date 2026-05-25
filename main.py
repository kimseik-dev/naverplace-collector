"""
네이버 모바일 플레이스 수집기 — 진입점

사용 예:
    python main.py 강남맛집
    python main.py 강남미용실 --limit 30
    python main.py 강남맛집 --no-headless    # 브라우저 창 보면서 디버깅

학습/연구 목적으로만 사용. 네이버 약관과 robots.txt를 준수하세요.
"""

import argparse
import asyncio
import sys

from src.scraper import fetch_place_list, to_dict_list
from src.exporter import export_to_xlsx


def parse_args():
    p = argparse.ArgumentParser(description="네이버 플레이스 스크래퍼 (학습용)")
    p.add_argument("query", help="검색 키워드 (예: 강남맛집, 강남미용실)")
    p.add_argument("--limit", type=int, default=100,
                   help="최대 수집 개수 (기본 100, 네이버 제공 한계까지)")
    p.add_argument("--category", default=None,
                   help="카테고리 강제 지정 (restaurant/hairshop/beautysalon/hospital/pharmacy). "
                        "생략 시 키워드에서 자동 추론")
    p.add_argument("--no-headless", action="store_true", help="브라우저 창 표시")
    p.add_argument("--out", default="output", help="출력 폴더 (기본 output)")
    p.add_argument("--no-enrich-phones", action="store_true",
                   help="전화번호 누락 시 상세 페이지 보강 생략 (빠르지만 일부 카테고리는 전화 비어있음)")
    return p.parse_args()


async def main_async(args):
    print(f"[START] 키워드='{args.query}', 목표={args.limit}개, 카테고리={args.category or '자동'}")
    places = await fetch_place_list(
        query=args.query,
        limit=args.limit,
        headless=not args.no_headless,
        category=args.category,
        enrich_phones=not args.no_enrich_phones,
    )

    if not places:
        print("[FAIL] 수집 결과가 0건입니다. 셀렉터 변경 또는 차단 가능성을 확인하세요.")
        sys.exit(1)

    out_file = export_to_xlsx(to_dict_list(places), query=args.query, out_dir=args.out)
    print(f"\n[DONE] 총 {len(places)}건 수집 완료")
    print(f"[FILE] {out_file.resolve()}")


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] 사용자가 중단했습니다.")
        sys.exit(130)


if __name__ == "__main__":
    main()
