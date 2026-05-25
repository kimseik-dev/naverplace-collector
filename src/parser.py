"""
HTML 파싱 모듈 (2026-05 기준 검증된 셀렉터)

네이버 클래스명은 자주 바뀝니다. 매칭 실패 시 debug_dom.py 로 최신 클래스 확인 필요.
"""

import re
from bs4 import BeautifulSoup


# m.search.naver.com 의 플레이스 카드 — 카테고리별 클래스가 다름
# 음식점: li.UEzoS / span.TYaxT
# 미용실/뷰티: li.p0FrU / span.O_Uah
_CARD_SELECTORS = ["li.UEzoS", "li.p0FrU", "li.VLTHu"]
_NAME_SELECTORS = ["span.TYaxT", "span.O_Uah", "span.YwYLL", "span.place_bluelink"]
_CATEGORY_SELECTORS = ["span.KCMnt", "span.YzBgS"]
_REVIEW_SELECTORS = ["span.h69bs", "span.piUxu", "span.MVx6e"]

# 카드 안에서 place_id 추출용 링크 패턴
_PLACE_ID_RE = re.compile(r"/(restaurant|place|hairshop|beauty|beautysalon)/(\d+)")


def _first_match(card, selectors):
    for sel in selectors:
        el = card.select_one(sel)
        if el:
            return el
    return None


def parse_place_list(html: str, limit: int = 50) -> list[dict]:
    """m.search.naver.com 결과의 플레이스 카드 파싱 (음식점/미용실 등 다중 카테고리)."""
    soup = BeautifulSoup(html, "lxml")

    cards = []
    matched_sel = None
    for sel in _CARD_SELECTORS:
        found = soup.select(sel)
        if found:
            cards = found
            matched_sel = sel
            break

    if not cards:
        print(f"[WARN] 카드 셀렉터 매칭 실패 (시도: {_CARD_SELECTORS})")
        return []

    print(f"[INFO] 카드 셀렉터 '{matched_sel}' 매칭, {len(cards)}개 발견")

    results = []
    for card in cards[:limit]:
        name_el = _first_match(card, _NAME_SELECTORS)
        if not name_el:
            continue

        # place_id 추출
        place_id, category_url = "", "restaurant"
        for a in card.find_all("a", href=True):
            m = _PLACE_ID_RE.search(a["href"])
            if m:
                category_url = m.group(1)
                place_id = m.group(2)
                break

        # 카테고리 표시명
        cat_el = _first_match(card, _CATEGORY_SELECTORS)
        category = cat_el.get_text(strip=True) if cat_el else ""

        # 리뷰 수 — "리뷰1,671" 또는 "방문자 리뷰6,388"
        visitor_review = ""
        for sel in _REVIEW_SELECTORS:
            for rv in card.select(sel):
                t = rv.get_text(" ", strip=True)
                m = re.search(r"리뷰\s*([\d,]+)", t)
                if m:
                    visitor_review = m.group(1)
                    break
            if visitor_review:
                break

        # 광고 여부 — 카드 내 "광고" 뱃지 텍스트
        text = card.get_text(" ", strip=True)
        is_ad = "광고" in text[:120]  # 카드 상단에 광고 뱃지가 위치

        results.append({
            "name": name_el.get_text(strip=True),
            "category": category,
            "place_id": place_id,
            "category_path": category_url,
            "place_url": f"https://m.place.naver.com/{category_url}/{place_id}/home" if place_id else "",
            "visitor_review": visitor_review,
            "blog_review": "",      # m.search 에서는 분리 표시 없음 → 상세에서 보강
            "is_ad": is_ad,
            "address": "",
            "phone": "",
        })

    return results


# ── 상세 페이지 (pcmap.place.naver.com 데스크탑 렌더링) ───────────────

_ADDR_SELECTORS = ["span.LDgIH", "span._2yqUQ"]      # 구버전 호환용
_PHONE_SELECTORS = ["span.xlx7Q", "span._3ZFi6"]
_INFO_BLOCK_SEL = ".O8qbU"                            # "주소\n...", "전화\n..." 등의 블록
_PHONE_RE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")
_ADDR_RE = re.compile(r"(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\s+\S+(?:로|길|동|읍|면)[^\n]{0,80}")
_BLOG_REVIEW_RE = re.compile(r"블로그리뷰\s*([\d,]+)")
_VISITOR_REVIEW_RE = re.compile(r"방문자리뷰\s*([\d,]+)")


def parse_place_detail(html: str) -> dict:
    """상세 페이지에서 주소, 전화번호, 분리된 리뷰 수 추출."""
    soup = BeautifulSoup(html, "lxml")

    # ── 주소 ──
    address = ""
    # 1) 구버전 직접 셀렉터
    addr_el = _first_match(soup, _ADDR_SELECTORS)
    if addr_el:
        address = addr_el.get_text(" ", strip=True)
    # 2) .O8qbU 블록 중 "주소"로 시작하는 것
    if not address:
        for block in soup.select(_INFO_BLOCK_SEL):
            t = block.get_text("\n", strip=True)
            if t.startswith("주소"):
                lines = [l for l in t.split("\n") if l]
                if len(lines) >= 2:
                    address = lines[1].strip()
                    break
    # 3) 정규식 폴백
    if not address:
        m = _ADDR_RE.search(soup.get_text(" ", strip=True))
        if m:
            address = m.group(0).strip()

    # ── 전화번호 ──
    phone = ""
    phone_el = _first_match(soup, _PHONE_SELECTORS)
    if phone_el:
        phone = phone_el.get_text(strip=True)
    if not phone:
        tel = soup.select_one("a[href^='tel:']")
        if tel:
            phone = tel.get("href", "").replace("tel:", "").strip()
    if not phone:
        # 폴백: 텍스트에서 패턴 검색
        text = soup.get_text(" ", strip=True)
        m = _PHONE_RE.search(text)
        if m:
            phone = m.group(0)

    # ── 분리된 리뷰 수 ──
    full_text = soup.get_text(" ", strip=True)
    visitor = ""
    blog = ""
    m = _VISITOR_REVIEW_RE.search(full_text)
    if m:
        visitor = m.group(1)
    m = _BLOG_REVIEW_RE.search(full_text)
    if m:
        blog = m.group(1)

    return {
        "address": address,
        "phone": phone,
        "visitor_review_detail": visitor,
        "blog_review_detail": blog,
    }
