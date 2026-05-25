"""
네이버 플레이스 스크래퍼 — GraphQL 응답 가로채기 방식 (최대 100개+)

전략:
  1. pcmap.place.naver.com 페이지 로드 (stealth 적용)
  2. 초기 SSR 의 window.__APOLLO_STATE__ 에서 첫 ~50개 추출
  3. 페이지 버튼 클릭으로 추가 데이터를 GraphQL 응답 가로채기로 수집
     - POST https://pcmap-api.place.naver.com/graphql 의 응답을 listening
     - response.placeList.businesses.items 추출
  4. DOM 순서대로 카드 이름을 매겨 rank 부여, name으로 데이터 매칭
  5. 다음페이지가 disabled 되거나 limit 도달 시 종료

학습/연구 목적으로만 사용하세요.
"""

import asyncio
import json
import random
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, BrowserContext


DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PCMAP_LIST_URL = "https://pcmap.place.naver.com/{cat}/list?query={q}"

_CATEGORY_KEYWORDS = [
    ("restaurant",  ["맛집", "식당", "음식점", "레스토랑", "베이커리", "디저트",
                     "분식", "치킨", "피자", "한식", "양식", "중식", "일식", "포차", "술집"]),
    ("hairshop",    ["미용실", "헤어샵", "헤어샾", "헤어", "살롱", "미용", "펌"]),
    ("beautysalon", ["네일", "왁싱", "피부관리", "에스테틱", "스파", "마사지"]),
    ("hospital",    ["병원", "의원", "치과", "한의원", "성형외과", "피부과", "내과"]),
    ("pharmacy",    ["약국"]),
    ("cafe",        ["카페", "커피숍"]),
]


def infer_category(query: str) -> str:
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(k in query for k in kws):
            return cat
    return "restaurant"


@dataclass
class PlaceInfo:
    rank: int = 0
    name: str = ""
    category: str = ""
    address: str = ""
    phone: str = ""
    visitor_review: str = ""
    blog_review: str = ""
    place_id: str = ""
    category_path: str = ""
    place_url: str = ""
    is_ad: bool = False
    # 지도 뷰용 좌표 (Naver 는 x=경도, y=위도)
    longitude: float = 0.0
    latitude: float = 0.0


async def _polite(min_s: float = 1.5, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _make_desktop_context(browser: Browser) -> BrowserContext:
    ctx = await browser.new_context(
        user_agent=DESKTOP_UA,
        viewport={"width": 1920, "height": 1080},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        },
    )
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    """)
    return ctx


async def _warm_up(context: BrowserContext) -> None:
    page = await context.new_page()
    try:
        await page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=15000)
        await _polite(1.5, 2.5)
    except Exception:
        pass
    finally:
        await page.close()


def _is_business_entry(value: dict) -> bool:
    """Apollo state 의 entry 가 업체 데이터인지 판별."""
    if not isinstance(value, dict):
        return False
    typename = value.get("__typename", "")
    # 카테고리별 타입명: RestaurantBusinessSummary, BeautySummary, HairshopSummary, 광고는 ~AdSummary
    if any(suffix in typename for suffix in ("Summary", "ListBusinessesItem", "BusinessItem")):
        return bool(value.get("name") and (value.get("id") or value.get("apolloCacheId")))
    return False


def _extract_businesses_from_apollo(state: dict) -> list[dict]:
    """Apollo state 에서 업체 entry 들을 list 로 추출."""
    return [v for v in state.values() if _is_business_entry(v)]


def _extract_businesses_from_graphql(payload: dict) -> list[dict]:
    """GraphQL 응답에서 업체 items 추출. 다양한 응답 구조를 모두 처리."""
    result = []
    operations = payload if isinstance(payload, list) else [payload]
    for op in operations:
        data = op.get("data") or {}

        # 1) data.businesses.items 직접 (미용실/뷰티/병원 등)
        biz = data.get("businesses")
        if isinstance(biz, dict) and "items" in biz:
            for item in biz["items"] or []:
                if item and item.get("name"):
                    result.append(item)

        # 2) data.{category}.businesses.items (음식점/카페 등)
        for key in ("restaurants", "hairshops", "beautysalons", "hospitals",
                    "pharmacies", "cafes", "places"):
            obj = data.get(key)
            if not isinstance(obj, dict):
                continue
            businesses = obj.get("businesses")
            if isinstance(businesses, dict) and "items" in businesses:
                for item in businesses["items"] or []:
                    if item and item.get("name"):
                        result.append(item)

        # 3) data.adBusinesses.items (광고)
        ad = data.get("adBusinesses") or data.get("getAdBusinessList")
        if isinstance(ad, dict):
            items = ad.get("items") or []
            for item in items:
                if item and item.get("name"):
                    result.append(item)
    return result


def _build_place_info(rank: int, name: str, entry: dict | None,
                      category_path: str) -> PlaceInfo:
    info = PlaceInfo(rank=rank, name=name, category_path=category_path)
    if not entry:
        return info

    typename = entry.get("__typename", "")
    info.is_ad = "Ad" in typename or entry.get("adId") is not None
    info.place_id = str(entry.get("id") or entry.get("apolloCacheId") or "")
    info.category = entry.get("category") or ""

    road = entry.get("roadAddress") or ""
    common = entry.get("commonAddress") or ""
    full = entry.get("fullAddress") or ""
    addr_jibun = entry.get("address") or ""   # 지번 (예: "도곡동 957-11")
    if road and common:
        info.address = f"{common} {road}".strip()
    elif full:
        info.address = full
    elif road and addr_jibun:
        # 시도/구가 없으면 지번에서 추출 → "도곡동 957-11" + " | " + 도로명
        info.address = f"{addr_jibun} ({road})"
    elif road:
        info.address = road
    elif common:
        info.address = common
    elif addr_jibun:
        info.address = addr_jibun

    info.phone = entry.get("phone") or entry.get("virtualPhone") or ""

    visitor = entry.get("visitorReviewCount")
    blog = entry.get("blogCafeReviewCount")
    info.visitor_review = str(visitor) if visitor not in (None, 0) else ""
    info.blog_review = str(blog) if blog not in (None, 0) else ""

    if info.place_id:
        biz_cat = entry.get("businessCategory") or category_path
        info.place_url = f"https://m.place.naver.com/{biz_cat}/{info.place_id}/home"

    # 좌표 (Naver: x=경도, y=위도)
    try:
        x = entry.get("x")
        y = entry.get("y")
        if x is not None:
            info.longitude = float(x)
        if y is not None:
            info.latitude = float(y)
    except (TypeError, ValueError):
        pass

    return info


async def _enrich_phone(context: BrowserContext, place: PlaceInfo) -> None:
    """전화번호가 비어있으면 상세 페이지에서 추출."""
    if place.phone or not place.place_id:
        return
    cat = place.category_path or "restaurant"
    url = f"https://pcmap.place.naver.com/{cat}/{place.place_id}/home"
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        try:
            await page.wait_for_selector("span.xlx7Q, a[href^='tel:']", timeout=6000)
        except Exception:
            pass
        # 직접 텍스트 추출
        for sel in ["span.xlx7Q", "a[href^='tel:']"]:
            els = await page.locator(sel).all()
            for el in els:
                try:
                    if sel.startswith("a"):
                        href = await el.get_attribute("href")
                        if href:
                            place.phone = href.replace("tel:", "").strip()
                            return
                    else:
                        t = await el.inner_text()
                        if t and any(c.isdigit() for c in t):
                            place.phone = t.strip()
                            return
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        await page.close()


# 진행 상황 콜백 시그니처:
#   callback(stage, current, total, message)
#     stage: "list" | "enrich" | "done"
#     current/total: 진행 카운트
#     message: 사람이 읽을 수 있는 상태 메시지
ProgressCallback = Callable[[str, int, int, str], None]


def _safe_progress(cb: Optional[ProgressCallback],
                   stage: str, current: int, total: int, message: str) -> None:
    if cb is None:
        return
    try:
        cb(stage, current, total, message)
    except Exception:
        pass


async def fetch_place_list(
    query: str,
    limit: int = 100,
    headless: bool = True,
    category: str | None = None,
    enrich_phones: bool = True,
    progress: Optional[ProgressCallback] = None,
) -> list[PlaceInfo]:
    """GraphQL 응답 가로채기 방식으로 플레이스 목록 수집.

    Args:
        enrich_phones: True면 phone이 비어있는 업체를 상세 페이지에서 보강.
                       restaurant 는 list API 에 phone 이 포함되어 거의 불필요.
                       hairshop/beautysalon 등은 이 옵션이 켜져야 phone 수집됨.
        progress: 진행 상황 콜백 (Streamlit 등에서 사용)
    """
    if category is None:
        category = infer_category(query)
        print(f"[INFO] 카테고리 자동 추론: '{category}' (키워드: {query!r})")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        try:
            ctx = await _make_desktop_context(browser)
            await _warm_up(ctx)
            page = await ctx.new_page()

            # GraphQL 응답 캡처용 버퍼
            extra_entries: list[dict] = []

            async def handle_response(response):
                if "pcmap-api.place.naver.com/graphql" in response.url:
                    try:
                        body = await response.json()
                        items = _extract_businesses_from_graphql(body)
                        if items:
                            extra_entries.extend(items)
                    except Exception:
                        pass

            page.on("response", lambda r: asyncio.create_task(handle_response(r)))

            url = PCMAP_LIST_URL.format(cat=category, q=quote(query))
            print(f"[STEP1] {category} 목록 페이지 접속")
            print(f"        {url}")
            _safe_progress(progress, "list", 0, limit, f"{category} 카테고리 목록 페이지 접속 중...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await _polite(2.5, 3.5)

            # SSR Apollo state 에서 초기 entry 추출
            initial_state = await page.evaluate("window.__APOLLO_STATE__ || {}")
            initial_entries = _extract_businesses_from_apollo(initial_state)
            print(f"        SSR Apollo state: {len(initial_entries)}개 업체 entry 발견")

            # name → entry 인덱스 (광고가 아닌 것 우선)
            entry_by_name: dict[str, dict] = {}
            def add_entries(entries: list[dict]) -> None:
                for e in entries:
                    n = e.get("name")
                    if not n:
                        continue
                    if n in entry_by_name:
                        old_ad = "Ad" in entry_by_name[n].get("__typename", "")
                        new_ad = "Ad" in e.get("__typename", "")
                        if old_ad and not new_ad:
                            entry_by_name[n] = e
                    else:
                        entry_by_name[n] = e
            add_entries(initial_entries)

            # 페이지 순회
            collected: list[PlaceInfo] = []
            seen_keys: set[str] = set()
            page_idx = 1
            max_pages = 15

            while page_idx <= max_pages and len(collected) < limit:
                try:
                    await page.wait_for_selector("li.UEzoS, li.p0FrU", timeout=8000)
                except Exception:
                    print(f"  [WARN] page {page_idx}: 카드 로드 타임아웃")
                    break

                # 현재 페이지 DOM 카드 이름
                # 카드 셀렉터는 카테고리마다 다름. 다중 셀렉터로 시도.
                names: list[str] = []
                for sel in ["li.UEzoS span.TYaxT", "li.p0FrU span.O_Uah"]:
                    if await page.locator(sel).count() > 0:
                        names = await page.locator(sel).all_inner_texts()
                        break
                names = [n.strip() for n in names if n.strip()]

                # 응답 가로채기로 추가된 entries 인덱스에 병합
                if extra_entries:
                    add_entries(extra_entries)
                    extra_entries.clear()

                new_count = 0
                for name in names:
                    rank = len(collected) + 1
                    entry = entry_by_name.get(name)
                    info = _build_place_info(rank, name, entry, category)
                    key = info.place_id or f"_noid_{name}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    collected.append(info)
                    new_count += 1
                    if len(collected) >= limit:
                        break

                print(f"  ✓ page {page_idx}: DOM {len(names)}개, 신규 {new_count}개, "
                      f"누적 {len(collected)}/{limit}  (인덱스 {len(entry_by_name)})")
                _safe_progress(progress, "list", len(collected), limit,
                               f"페이지 {page_idx} 수집 중 (누적 {len(collected)}개)")

                if len(collected) >= limit:
                    break

                # 다음 페이지로 — 보이는 페이지 번호 우선, 아니면 "다음페이지"
                next_num = str(page_idx + 1)
                next_loc = page.locator(f'a.mBN2s:has-text("{next_num}")')
                if await next_loc.count() == 0:
                    arrow = page.locator('a.eUTV2:has-text("다음페이지")')
                    if await arrow.count() == 0 or \
                       (await arrow.first.get_attribute("aria-disabled")) == "true":
                        print(f"  → 더 이상 페이지 없음 (마지막: {page_idx})")
                        break
                    await arrow.first.click()
                else:
                    await next_loc.first.click()

                page_idx += 1
                # 다음 페이지 응답이 들어올 시간 + 인간적 딜레이
                await _polite(2.5, 4.0)

            await page.close()
            await ctx.close()

            # 전화번호가 비어있는 항목을 상세 페이지에서 보강 (미용실 등)
            missing = [p for p in collected if p.place_id and not p.phone]
            if enrich_phones and missing:
                print(f"\n[STEP2] 전화번호 누락 {len(missing)}건 — 상세 페이지에서 보강")
                _safe_progress(progress, "enrich", 0, len(missing),
                               f"전화번호 누락 {len(missing)}건 보강 시작")
                # 5건마다 컨텍스트 회전 (봇 탐지 회피)
                detail_ctx = None
                for i, place in enumerate(missing):
                    if detail_ctx is None or i % 5 == 0:
                        if detail_ctx is not None:
                            await detail_ctx.close()
                            await _polite(2.0, 3.5)
                        detail_ctx = await _make_desktop_context(browser)
                    await _enrich_phone(detail_ctx, place)
                    status = place.phone if place.phone else "(없음)"
                    print(f"  [{i+1:3d}/{len(missing)}] {place.name[:22]:22s}  📞 {status}")
                    _safe_progress(progress, "enrich", i + 1, len(missing),
                                   f"{place.name} 전화번호 보강 ({i+1}/{len(missing)})")
                    await _polite(1.0, 1.8)
                if detail_ctx is not None:
                    await detail_ctx.close()

            _safe_progress(progress, "done", len(collected), len(collected),
                           f"총 {len(collected)}개 수집 완료")
            print(f"\n[DONE] 총 {len(collected)}개 수집")
            for info in collected:
                ad_mark = "[광고]" if info.is_ad else "      "
                phone = info.phone if info.phone else "-"
                addr = info.address[:30] if info.address else "-"
                print(f"  {ad_mark} [{info.rank:3d}] {info.name[:22]:22s}  "
                      f"📞 {phone:16s}  📍 {addr}")

            return collected
        finally:
            await browser.close()


def to_dict_list(places: list[PlaceInfo]) -> list[dict]:
    return [asdict(p) for p in places]
