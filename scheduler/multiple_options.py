# scheduler/multiple_options.py
import logging
import asyncio
import copy
import time
from typing import Dict, Any, List, Optional, Tuple
import json


# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('multiple_options')

def extract_region_context_from_input(voice_input: str) -> str:
    """음성 입력에서 지역 맥락 추출 - KOREA_REGIONS 활용"""
    voice_lower = voice_input.lower()
    
    region_scores = {}
    
    # 🔥 KOREA_REGIONS를 활용한 체계적인 지역 검색
    for region_name, districts in KOREA_REGIONS.items():
        # 시/도명 체크 (완전명과 축약명 모두)
        region_short = region_name.replace('특별시', '').replace('광역시', '').replace('특별자치시', '').replace('특별자치도', '').replace('도', '')
        
        # 1) 직접적인 시/도명 매칭 (높은 점수)
        if region_short in voice_lower or region_name in voice_lower:
            region_scores[region_name] = region_scores.get(region_name, 0) + 10
            logger.info(f"🎯 직접 지역명 발견: '{region_short}' → {region_name}")
        
        # 2) 구/시/군명으로 지역 추론 (중간 점수)
        for district in districts:
            if district in voice_lower:
                region_scores[region_name] = region_scores.get(region_name, 0) + 5
                logger.info(f"🏘️ 구/시/군명 발견: '{district}' → {region_name}")
    
    # 3) 유명 장소/역명으로 지역 추론 (낮은 점수)
    famous_places = {
        # 부산 관련
        "부산역": "부산광역시", "서면": "부산광역시", "해운대": "부산광역시", 
        "광안리": "부산광역시", "장전역": "부산광역시", "센텀시티": "부산광역시",
        "남포동": "부산광역시", "기장": "부산광역시",
        
        # 서울 관련  
        "강남역": "서울특별시", "홍대": "서울특별시", "명동": "서울특별시",
        "잠실": "서울특별시", "신촌": "서울특별시", "이태원": "서울특별시",
        "강남": "서울특별시", "서울역": "서울특별시",
        
        # 대구 관련
        "동성로": "대구광역시", "수성구": "대구광역시",
        
        # 인천 관련
        "송도": "인천광역시", "부평": "인천광역시",
        
        # 기타 유명 장소들
        "제주공항": "제주특별자치도", "울산대학교": "울산광역시"
    }
    
    for place, region in famous_places.items():
        if place in voice_lower:
            region_scores[region] = region_scores.get(region, 0) + 3
            logger.info(f"🏛️ 유명 장소 발견: '{place}' → {region}")
    
    # 가장 높은 점수의 지역 반환
    if region_scores:
        best_region = max(region_scores.keys(), key=lambda k: region_scores[k])
        logger.info(f"🗺️ 지역 맥락 추출 완료: {best_region} (점수: {region_scores[best_region]})")
        logger.info(f"   전체 점수: {region_scores}")
        return best_region
    
    # 기본값은 서울
    logger.info("⚠️ 지역 맥락 추출 실패, 서울 기본값 사용")
    return "서울특별시"

class MultipleOptionsGenerator:
    """다중 옵션 생성기 - 3중 API와 5가지 선택 전략을 활용한 스마트 옵션 제공"""
    
    def __init__(self, triple_api_service):
        """다중 옵션 생성기 초기화"""
        self.triple_api_service = triple_api_service
        self.voice_input = ""  # 🔥 음성 입력 저장
        
        # 검색 가능한 키워드 정의
        self.searchable_keywords = [
            # 음식 관련
            "식사", "저녁", "점심", "아침", "밥", "식당", "맛집", "카페", "커피", "술", "회식",
            "디저트", "간식", "브런치", "야식", "치킨", "피자", "햄버거", "중식", "일식", "양식", "한식",
            
            # 활동/장소 관련
            "쇼핑", "영화", "놀이", "게임", "노래방", "pc방", "찜질방", "마사지", "헬스", "운동",
            "미용실", "네일", "병원", "약국", "은행", "관광", "여행", "구경", "산책"
        ]
        
        # 구체적 장소 키워드 (검색 제외 대상)
        self.specific_place_keywords = [
            "역", "공항", "터미널", "대학교", "학교", "회사", "사무실", "집", "아파트", "빌딩", 
            "센터", "타워", "플라자", "몰", "마트", "백화점", "호텔", "병원", "시청", "구청"
        ]
        
        logger.info("🎯 다중 옵션 생성기 초기화 완료")
        logger.info(f"   검색 가능 키워드: {len(self.searchable_keywords)}개")
        logger.info(f"   구체적 장소 키워드: {len(self.specific_place_keywords)}개")
    
    async def generate_options(self, schedule_data: Dict[str, Any], voice_input: str = "") -> Dict[str, Any]:
        """다중 옵션 생성 메인 함수"""
        logger.info("🚀 다중 옵션 생성 시스템 시작")
        start_time = time.time()
        
        self.voice_input = voice_input  # 🔥 음성 입력 저장
        
        try:
            # 1단계: 검색 가능한 항목 식별
            logger.info("📍 1단계: 검색 가능한 항목 식별")
            searchable_items = self._identify_searchable_items(schedule_data)
            
            if not searchable_items:
                logger.info("⚠️ 검색 가능한 항목이 없어서 원본 일정 그대로 5개 옵션 생성")
                return self._create_simple_options(schedule_data)
            
            # 2단계: 3중 API로 다중 후보 검색
            logger.info("📍 2단계: 3중 API 다중 후보 검색")
            search_results = await self._search_multiple_candidates(searchable_items)
            
            # 3단계: 5가지 선택 전략 적용
            logger.info("📍 3단계: 5가지 선택 전략 적용")
            strategy_results = self._apply_selection_strategies(search_results)
            
            # 4단계: 원본 일정과 옵션 조합
            logger.info("📍 4단계: 원본 일정과 옵션 조합")
            final_options = self._combine_with_original(schedule_data, searchable_items, strategy_results)
            
            elapsed = time.time() - start_time
            logger.info(f"🎉 다중 옵션 생성 완료: {elapsed:.2f}초")
            logger.info(f"   최종 옵션 수: {len(final_options.get('options', []))}개")
            
            return final_options
            
        except Exception as e:
            logger.error(f"❌ 다중 옵션 생성 실패: {e}")
            return self._create_simple_options(schedule_data)
    
    def _identify_searchable_items(self, schedule_data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """검색 가능한 항목 식별"""
        logger.info("🔍 검색 가능한 항목 식별 시작")
        
        searchable_items = []
        all_schedules = []
        all_schedules.extend(schedule_data.get("fixedSchedules", []))
        all_schedules.extend(schedule_data.get("flexibleSchedules", []))
        
        logger.info(f"   전체 일정 수: {len(all_schedules)}개")
        
        for i, schedule in enumerate(all_schedules):
            name = schedule.get("name", "")
            location = schedule.get("location", "")
            
            logger.info(f"   일정 {i+1} 분석: '{name}' / '{location}'")
            
            if self._is_searchable_item(schedule):
                search_query = self._create_search_query(name, location)
                searchable_items.append((search_query, schedule))
                logger.info(f"      🎯 검색 대상으로 추가: '{search_query}'")
            else:
                logger.info(f"      ❌ 검색 제외")
        
        logger.info(f"✅ 검색 가능한 항목 식별 완료: {len(searchable_items)}개 발견")
        return searchable_items
    
    def _is_searchable_item(self, schedule: Dict[str, Any]) -> bool:
        """검색 가능한 항목인지 판단 - 더 포괄적으로 수정"""
        name = schedule.get("name", "").lower()
        location = schedule.get("location", "").lower()
        
        # 🔥 모든 일정을 검색 대상으로 변경 (위치가 비어있거나 불완전하면)
        
        # 이미 완전한 주소가 있는 경우만 제외
        if location and len(location) > 10 and any(keyword in location for keyword in ["구", "시", "동", "로", "길"]):
            logger.info(f"      ❌ 완전한 주소 보유로 검색 제외: '{name}' / '{location}'")
            return False
        
        # 검색 가능한 키워드가 있는지 확인
        searchable_keywords = [
            # 음식 관련
            "식사", "저녁", "점심", "아침", "밥", "식당", "맛집", "카페", "커피",
            # 장소 관련 (역도 포함하도록 수정)
            "역", "터미널", "공항", "호텔", "마트", "병원", "학교", "대학교"
        ]
        
        has_searchable = any(keyword in name for keyword in searchable_keywords)
        
        if has_searchable:
            logger.info(f"      ✅ 검색 가능 키워드 발견: '{name}' (키워드: {[k for k in searchable_keywords if k in name]})")
            return True
        else:
            logger.info(f"      ❌ 검색 가능 키워드 없음: '{name}'")
            return False
    
    def _create_search_query(self, name: str, location: str) -> str:
        """검색 쿼리 생성 - 지역 맥락 고려"""
        logger.info(f"       🔍 검색 쿼리 생성: 이름='{name}', 위치='{location}'")
        
        # 🔥 지역 맥락 추출 (음성 입력에서)
        region_context = extract_region_context_from_input(self.voice_input)
        
        # 카테고리 추출
        category = self._extract_category(name)
        
        if location and location.strip():
            # 위치 정보가 있으면 그대로 사용
            query = f"{location} {category}"
            logger.info(f"         📍 위치 기반 쿼리: '{query}'")
        else:
            # 위치 정보가 없으면 추출된 지역 사용
            region_short = region_context.replace('특별시', '').replace('광역시', '')
            query = f"{region_short} {category}"
            logger.info(f"         📍 지역 맥락 기반 쿼리: '{query}' (추출된 지역: {region_context})")
        
        logger.info(f"         🎯 최종 검색 쿼리: '{query}'")
        return query
    
    def _extract_category(self, name: str) -> str:
        """장소명에서 카테고리 추출"""
        name_lower = name.lower()
        
        # 카테고리 매핑
        category_mappings = {
            "맛집": ["식사", "저녁", "점심", "아침", "밥", "식당", "맛집"],
            "카페": ["카페", "커피", "디저트"],
            "술집": ["술", "회식", "맥주", "소주"],
            "쇼핑": ["쇼핑", "옷", "구매"],
            "놀이": ["놀이", "게임", "오락"],
            "휴식": ["휴식", "마사지", "찜질방"],
            "운동": ["운동", "헬스", "체육관"],
            "병원": ["병원", "의원", "치료"],
            "역": ["역", "지하철", "전철"],
            "공항": ["공항", "비행기"],
            "호텔": ["호텔", "숙박", "펜션"]
        }
        
        for category, keywords in category_mappings.items():
            if any(keyword in name_lower for keyword in keywords):
                logger.info(f"         🏷️ 카테고리 추출: {category}")
                return category
        
        logger.info(f"         🏷️ 기본 카테고리 사용: 장소")
        return "장소"
    
    async def _search_multiple_candidates(self, searchable_items: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """3중 API로 다중 후보 검색"""
        logger.info("🚀 3중 API 다중 후보 검색 시작")
        
        all_results = {}
        
        for i, (query, original_schedule) in enumerate(searchable_items):
            logger.info(f"📍 항목 {i+1} 검색 시작: '{query}'")
            
            candidates = []
            
            # Kakao 다중 검색 (상위 3개)
            kakao_results = await self._search_kakao_multiple(query, limit=3)
            candidates.extend(kakao_results)
            logger.info(f"    🟡 Kakao 결과: {len(kakao_results)}개")
            
            # Google 다중 검색 (상위 2개)
            google_results = await self._search_google_multiple(query, limit=2)
            candidates.extend(google_results)
            logger.info(f"    🔵 Google 결과: {len(google_results)}개")
            
            # Foursquare 다중 검색 (상위 2개)
            foursquare_results = await self._search_foursquare_multiple(query, limit=2)
            candidates.extend(foursquare_results)
            logger.info(f"    🟣 Foursquare 결과: {len(foursquare_results)}개")
            
            # 후보 품질 검증 및 중복 제거
            valid_candidates = self._validate_and_dedupe_candidates(candidates)
            logger.info(f"✅ 항목 {i+1} 검색 완료: 총 {len(valid_candidates)}개 유효 후보")
            
            # 후보들 상세 로깅
            for j, candidate in enumerate(valid_candidates):
                logger.info(f"    후보 {j+1}: {candidate.get('name')} ({candidate.get('source')})")
                logger.info(f"      📍 {candidate.get('address')}")
                logger.info(f"      ⭐ 평점: {candidate.get('rating', 'None')}")
            
            all_results[query] = valid_candidates
        
        logger.info(f"🎉 전체 3중 API 검색 완료: {len(searchable_items)}개 항목, 총 {sum(len(results) for results in all_results.values())}개 후보")
        return all_results
    
    async def _search_kakao_multiple(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Kakao API 다중 검색"""
        logger.info(f"    🟡 Kakao 다중 검색: '{query}' (상위 {limit}개)")
        
        try:
            analysis = await self.triple_api_service.analyze_location_with_gpt(query)
            logger.info(f"    GPT 분석: {analysis.region} {analysis.district} - {analysis.place_name}")
            
            # 검색 전략 구성
            region_short = analysis.region.replace('특별시', '').replace('광역시', '')
            search_strategies = [
                f"{region_short} {analysis.district} {analysis.place_name}",
                f"{region_short} {analysis.place_name}",
                f"{analysis.place_name}"
            ]
            
            logger.info(f"    Kakao 검색 전략: {search_strategies}")
            
            results = []
            for strategy in search_strategies:
                try:
                    result = await self.triple_api_service.search_kakao(analysis)
                    if result:
                        results.append({
                            "name": result.name,
                            "address": result.address,
                            "latitude": result.latitude,
                            "longitude": result.longitude,
                            "source": "kakao",
                            "rating": None
                        })
                        logger.info(f"    검색 실행: '{strategy}'")
                        logger.info(f"      응답: {len(results)}개 문서")
                        
                        # 상위 몇 개만 처리
                        processed = 0
                        for doc in results[:limit]:
                            if processed >= limit:
                                break
                            
                            logger.info(f"      후보 {processed + 1}: {doc['name']} - {doc['address']}")
                            processed += 1
                        
                        break  # 성공하면 다음 전략 시도 안 함
                except Exception as e:
                    logger.error(f"    검색 오류 '{strategy}': {e}")
                    continue
            
            logger.info(f"    Kakao 검색 결과: {len(results)}개")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"❌ Kakao 다중 검색 오류: {e}")
            return []
    
    async def _search_google_multiple(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Google API 다중 검색"""
        logger.info(f"    🔵 Google 다중 검색: '{query}' (상위 {limit}개)")
        
        try:
            analysis = await self.triple_api_service.analyze_location_with_gpt(query)
            logger.info(f"    GPT 분석: {analysis.region} {analysis.district} - {analysis.place_name}")
            
            # 검색 전략 구성
            region_short = analysis.region.replace('특별시', '').replace('광역시', '')
            search_strategies = [
                f"{region_short} {analysis.district} {analysis.place_name}",
                f"{region_short} {analysis.place_name}"
            ]
            
            logger.info(f"    Google 검색 전략: {search_strategies}")
            
            results = []
            for strategy in search_strategies:
                try:
                    result = await self.triple_api_service.search_google(analysis)
                    if result:
                        results.append({
                            "name": result.name,
                            "address": result.address,
                            "latitude": result.latitude,
                            "longitude": result.longitude,
                            "source": "google",
                            "rating": result.rating
                        })
                        logger.info(f"    검색 실행: '{strategy}'")
                        logger.info(f"      응답: {len(results)}개 후보")
                        
                        for i, candidate in enumerate(results):
                            logger.info(f"      후보 {i + 1}: {candidate['name']} - 평점: {candidate.get('rating', 'None')}")
                        
                        if len(results) >= limit:
                            break
                            
                except Exception as e:
                    logger.error(f"    검색 오류 '{strategy}': {e}")
                    continue
            
            logger.info(f"    Google 검색 결과: {len(results)}개")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"❌ Google 다중 검색 오류: {e}")
            return []
    
    async def _search_foursquare_multiple(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """Foursquare API 다중 검색"""
        logger.info(f"    🟣 Foursquare 다중 검색: '{query}' (상위 {limit}개)")
        
        try:
            analysis = await self.triple_api_service.analyze_location_with_gpt(query)
            logger.info(f"    GPT 분석: {analysis.region} {analysis.district} - {analysis.place_name}")
            
            # 검색 전략 구성
            region_short = analysis.region.replace('특별시', '').replace('광역시', '')
            search_strategies = [
                f"{region_short} {analysis.place_name}",
                f"{analysis.place_name}"
            ]
            
            logger.info(f"    Foursquare 검색 전략: {search_strategies}")
            
            results = []
            for strategy in search_strategies:
                try:
                    result = await self.triple_api_service.search_foursquare(analysis)
                    if result:
                        results.append({
                            "name": result.name,
                            "address": result.address,
                            "latitude": result.latitude,
                            "longitude": result.longitude,
                            "source": "foursquare",
                            "rating": result.rating
                        })
                        logger.info(f"    검색 실행: '{strategy}'")
                        logger.info(f"      응답: {len(results)}개 장소")
                        
                        processed = 0
                        for place in results[:limit]:
                            if processed >= limit:
                                break
                            logger.info(f"      후보 {processed + 1}: {place['name']} - 평점: {place.get('rating', 'None')}")
                            processed += 1
                        
                        if len(results) >= limit:
                            break
                            
                except Exception as e:
                    logger.error(f"    검색 오류 '{strategy}': {e}")
                    continue
            
            logger.info(f"    Foursquare 검색 결과: {len(results)}개")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"❌ Foursquare 다중 검색 오류: {e}")
            return []
    
    def _validate_and_dedupe_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """후보 품질 검증 및 중복 제거"""
        logger.info(f"🧹 항목 {len(candidates)}개 후보 품질 검증 시작: {len(candidates)}개")
        
        valid_candidates = []
        seen_names = set()
        
        for i, candidate in enumerate(candidates):
            logger.info(f"    후보 {i+1} 검증: {candidate.get('name')}")
            
            # 1. 기본 정보 확인
            if not candidate.get('name') or not candidate.get('address'):
                logger.warning(f"      ❌ 기본 정보 누락")
                continue
            
            # 2. 중복 이름 제거
            name = candidate.get('name', '').strip()
            if name.lower() in seen_names:
                logger.warning(f"      ❌ 중복 이름: {name}")
                continue
            
            # 3. 유효한 후보로 인정
            seen_names.add(name.lower())
            valid_candidates.append(candidate)
            logger.info(f"      ✅ 유효한 후보: {name} ({candidate.get('source')})")
        
        logger.info(f"✅ 후보 품질 검증 완료: {len(valid_candidates)}개 유효 (원본: {len(candidates)}개)")
        return valid_candidates
    
    def _apply_selection_strategies(self, search_results: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, List[Dict[str, Any]]]]:
        """5가지 선택 전략 적용"""
        logger.info("🎯 5가지 선택 전략 적용 시작")
        
        strategies = [
            ("최고 평점", self._strategy_best_rating),
            ("가성비 중심", self._strategy_value_for_money),
            ("API 다양성", self._strategy_api_diversity),
            ("거리 최적화", self._strategy_distance_optimization),
            ("프리미엄 고급", self._strategy_premium_luxury)
        ]
        
        strategy_results = []
        
        for i, (strategy_name, strategy_func) in enumerate(strategies):
            logger.info(f"🎲 전략 {i+1}: {strategy_name} 적용 시작")
            
            try:
                selected = strategy_func(search_results)
                strategy_results.append(selected)
                logger.info(f"✅ 전략 {i+1} 완료: {len(selected)}개 장소 선택")
                
                # 선택된 장소들 로깅
                for j, (query, places) in enumerate(selected.items()):
                    for place in places:
                        logger.info(f"    항목 {j+1}: {place.get('name')} ({place.get('source')})")
                        
            except Exception as e:
                logger.error(f"❌ 전략 {i+1} 실패: {e}")
                # 실패 시 첫 번째 결과 사용
                strategy_results.append(self._strategy_fallback(search_results))
        
        logger.info(f"🎉 모든 선택 전략 적용 완료: {len(strategy_results)}개 옵션")
        return strategy_results
    
    def _strategy_best_rating(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """전략 1: 최고 평점"""
        logger.info("    🌟 최고 평점 전략 실행")
        
        selected = {}
        for query, candidates in search_results.items():
            logger.info(f"      항목 1: {len(candidates)}개 후보에서 최고 평점 선택")
            
            best_candidate = None
            best_rating = -1
            
            for candidate in candidates:
                rating = candidate.get('rating', 0) or 0
                logger.info(f"        {candidate.get('name')}: 평점 {rating}")
                
                if rating > best_rating:
                    best_rating = rating
                    best_candidate = candidate
                    logger.info(f"          🔥 현재 최고: {candidate.get('name')} (평점 {rating})")
            
            if best_candidate:
                selected[query] = [best_candidate]
                logger.info(f"      ✅ 선택됨: {best_candidate.get('name')} (평점 {best_rating})")
            else:
                selected[query] = candidates[:1] if candidates else []
        
        return selected
    
    def _strategy_value_for_money(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """전략 2: 가성비 중심"""
        logger.info("    💰 가성비 중심 전략 실행")
        
        selected = {}
        for query, candidates in search_results.items():
            logger.info(f"      항목 1: {len(candidates)}개 후보에서 가성비 선택")
            
            best_candidate = None
            best_value_score = -1
            
            for candidate in candidates:
                # 가성비 점수 계산 (평점 + API 신뢰도 보너스)
                rating = candidate.get('rating', 0) or 3.5  # 평점 없으면 기본 3.5
                source_bonus = {'google': 0.2, 'kakao': 0.1, 'foursquare': 0.0}.get(candidate.get('source'), 0)
                value_score = rating + source_bonus
                
                logger.info(f"        {candidate.get('name')}: 평점 {rating}, 소스 {candidate.get('source')}, 최종점수 {value_score}")
                
                if value_score > best_value_score:
                    best_value_score = value_score
                    best_candidate = candidate
                    logger.info(f"          🔥 현재 최고 가성비: {candidate.get('name')} (점수 {value_score})")
            
            if best_candidate:
                selected[query] = [best_candidate]
                logger.info(f"      ✅ 가성비 선택됨: {best_candidate.get('name')} (점수 {best_value_score})")
            else:
                selected[query] = candidates[:1] if candidates else []
        
        return selected
    
    def _strategy_api_diversity(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """전략 3: API 다양성"""
        logger.info("    🌈 API 다양성 전략 실행")
        
        selected = {}
        api_priority = ['kakao', 'google', 'foursquare']  # 우선순위
        
        for query, candidates in search_results.items():
            logger.info(f"      항목 1: API 다양성 선택")
            
            selected_candidate = None
            
            # 우선순위대로 API 검색
            for api in api_priority:
                logger.info(f"        우선 API: {api}")
                for candidate in candidates:
                    if candidate.get('source') == api:
                        selected_candidate = candidate
                        logger.info(f"          ✅ {api} 결과 발견: {candidate.get('name')}")
                        break
                if selected_candidate:
                    break
            
            # 못 찾으면 첫 번째 결과
            if not selected_candidate and candidates:
                selected_candidate = candidates[0]
            
            if selected_candidate:
                selected[query] = [selected_candidate]
                logger.info(f"      ✅ API 다양성 선택됨: {selected_candidate.get('name')} ({selected_candidate.get('source')})")
            else:
                selected[query] = []
        
        return selected
    
    def _strategy_distance_optimization(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """전략 4: 거리 최적화"""
        logger.info("    📍 거리 최적화 전략 실행")
        
        selected = {}
        # 참조 위치 (이전 일정의 위치 등을 고려해야 하지만, 현재는 간단하게)
        
        for query, candidates in search_results.items():
            logger.info(f"      항목 1: 거리 최적화 선택")
            logger.info(f"        참조 위치:")  # 실제로는 이전 일정 위치 사용
            
            best_candidate = None
            best_distance_score = -1
            
            for candidate in candidates:
                # 거리 점수 (현재는 임시로 100점 만점)
                distance_score = 100.0  # 실제로는 거리 계산 필요
                
                logger.info(f"        {candidate.get('name')}: 거리점수 {distance_score:.2f}")
                
                if distance_score > best_distance_score:
                    best_distance_score = distance_score
                    best_candidate = candidate
                    logger.info(f"          🔥 현재 최근접: {candidate.get('name')} (점수 {distance_score:.2f})")
            
            if best_candidate:
                selected[query] = [best_candidate]
                logger.info(f"      ✅ 거리 최적화 선택됨: {best_candidate.get('name')} (점수 {best_distance_score:.2f})")
            else:
                selected[query] = candidates[:1] if candidates else []
        
        return selected
    
    def _strategy_premium_luxury(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """전략 5: 프리미엄 고급"""
        logger.info("    👑 프리미엄 고급 전략 실행")
        
        selected = {}
        premium_keywords = ['호텔', '리조트', '프리미엄', '럭셔리', '고급', 'premium', 'luxury', 'hotel']
        
        for query, candidates in search_results.items():
            logger.info(f"      항목 1: 프리미엄 선택")
            
            best_candidate = None
            best_premium_score = -1
            
            for candidate in candidates:
                # 프리미엄 점수 계산
                premium_score = 0
                name = candidate.get('name', '').lower()
                address = candidate.get('address', '').lower()
                
                # 평점 기반 점수
                rating = candidate.get('rating', 0) or 0
                if rating >= 4.5:
                    premium_score += 3
                elif rating >= 4.0:
                    premium_score += 2
                elif rating >= 3.5:
                    premium_score += 1
                
                # 프리미엄 키워드 보너스
                for keyword in premium_keywords:
                    if keyword in name or keyword in address:
                        premium_score += 2
                        logger.info(f"          🏷️ 프리미엄 카테고리 '{keyword}' 발견")
                
                logger.info(f"        {candidate.get('name')}: 평점 {rating}, 프리미엄점수 {premium_score}")
                
                if premium_score > best_premium_score:
                    best_premium_score = premium_score
                    best_candidate = candidate
                    logger.info(f"          🔥 현재 최고 프리미엄: {candidate.get('name')} (점수 {premium_score})")
            
            if best_candidate:
                selected[query] = [best_candidate]
                logger.info(f"      ✅ 프리미엄 선택됨: {best_candidate.get('name')} (점수 {best_premium_score})")
            else:
                selected[query] = candidates[:1] if candidates else []
        
        return selected
    
    def _strategy_fallback(self, search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """폴백 전략: 첫 번째 결과 사용"""
        logger.info("    🔄 폴백 전략 실행")
        
        selected = {}
        for query, candidates in search_results.items():
            selected[query] = candidates[:1] if candidates else []
        
        return selected
    
    def _combine_with_original(self, schedule_data: Dict[str, Any], searchable_items: List[Tuple[str, Dict[str, Any]]], strategy_results: List[Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Any]:
        """원본 일정과 옵션 조합"""
        logger.info("🔧 원본 일정과 옵션 조합 시작")
        
        fixed_schedules = schedule_data.get("fixedSchedules", [])
        flexible_schedules = schedule_data.get("flexibleSchedules", [])
        
        logger.info(f"    원본 일정: 고정 {len(fixed_schedules)}개, 유연 {len(flexible_schedules)}개")
        logger.info(f"    검색 대상: {len(searchable_items)}개")
        logger.info(f"    생성할 옵션: {len(strategy_results)}개")
        
        options = []
        
        for i, strategy_result in enumerate(strategy_results):
            logger.info(f"🎯 옵션 {i+1} 생성: {['최고 평점', '가성비 중심', 'API 다양성', '거리 최적화', '프리미엄 고급'][i]}")
            
            # 원본 일정 복사
            option_fixed = copy.deepcopy(fixed_schedules)
            option_flexible = copy.deepcopy(flexible_schedules)
            
            # 검색 결과로 교체
            replacement_count = 0
            for query, original_schedule in searchable_items:
                if query in strategy_result and strategy_result[query]:
                    selected_place = strategy_result[query][0]  # 첫 번째 선택
                    
                    # 원본 일정에서 해당 스케줄 찾아서 교체
                    schedule_updated = False
                    
                    # 고정 일정에서 찾기
                    for schedule in option_fixed:
                        if (schedule.get("name") == original_schedule.get("name") and 
                            schedule.get("id") == original_schedule.get("id")):
                            
                            replacement_count += 1
                            logger.info(f"    교체 {replacement_count}: '{schedule.get('name')}' → '{selected_place.get('name')}'")
                            logger.info(f"      위치: {schedule.get('location')} → {selected_place.get('address')}")
                            
                            # ID 업데이트 (옵션별로 고유하게)
                            import time
                            new_id = f"{int(time.time() * 1000)}{i+1:02d}{replacement_count:02d}"
                            old_id = schedule.get("id", "N/A")
                            schedule["id"] = new_id
                            logger.info(f"        ID 업데이트: {old_id} → {new_id}")
                            
                            # 위치 정보 업데이트
                            schedule["location"] = selected_place.get("address", "")
                            schedule["latitude"] = selected_place.get("latitude", 37.5665)
                            schedule["longitude"] = selected_place.get("longitude", 126.9780)
                            
                            logger.info(f"        위치 업데이트 완료:")
                            logger.info(f"          주소: {selected_place.get('address', '')}")
                            logger.info(f"          좌표: {selected_place.get('latitude', 0):.4f}, {selected_place.get('longitude', 0):.4f}")
                            
                            schedule_updated = True
                            logger.info(f"      ✅ 고정 일정 업데이트 완료")
                            break
                    
                    # 유연 일정에서 찾기 (고정에서 못 찾았으면)
                    if not schedule_updated:
                        for schedule in option_flexible:
                            if (schedule.get("name") == original_schedule.get("name") and 
                                schedule.get("id") == original_schedule.get("id")):
                                
                                replacement_count += 1
                                logger.info(f"    교체 {replacement_count}: '{schedule.get('name')}' → '{selected_place.get('name')}'")
                                
                                # 위치 정보 업데이트
                                schedule["location"] = selected_place.get("address", "")
                                schedule["latitude"] = selected_place.get("latitude", 37.5665)
                                schedule["longitude"] = selected_place.get("longitude", 126.9780)
                                
                                logger.info(f"      ✅ 유연 일정 업데이트 완료")
                                break
            
            # 옵션 생성
            option = {
                "optionId": i + 1,
                "fixedSchedules": option_fixed,
                "flexibleSchedules": option_flexible
            }
            
            options.append(option)
            logger.info(f"✅ 옵션 {i+1} 생성 완료: 고정 {len(option_fixed)}개, 유연 {len(option_flexible)}개")
        
        result = {"options": options}
        logger.info(f"🎉 최종 다중 옵션 조합 완료: {len(options)}개 옵션")
        
        return result
    
    def _create_simple_options(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """간단한 옵션 생성 (검색 대상이 없을 때)"""
        logger.info("🔄 간단한 옵션 생성 (검색 없이)")
        
        options = []
        for i in range(5):
            # 원본 일정 복사
            option_fixed = copy.deepcopy(schedule_data.get("fixedSchedules", []))
            option_flexible = copy.deepcopy(schedule_data.get("flexibleSchedules", []))
            
            # ID만 옵션별로 업데이트
            for j, schedule in enumerate(option_fixed + option_flexible):
                import time
                new_id = f"{int(time.time() * 1000)}{i+1:02d}{j+1:02d}"
                schedule["id"] = new_id
            
            option = {
                "optionId": i + 1,
                "fixedSchedules": option_fixed,
                "flexibleSchedules": option_flexible
            }
            
            options.append(option)
        
        logger.info(f"✅ 간단한 옵션 생성 완료: {len(options)}개")
        return {"options": options}

KOREA_REGIONS = {
    "서울특별시": {"강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
               "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
               "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"},
    "부산광역시": {"강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구", "사상구",
               "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구"},
    "대구광역시": {"남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구"},
    "인천광역시": {"강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구"},
    "광주광역시": {"광산구", "남구", "동구", "북구", "서구"},
    "대전광역시": {"대덕구", "동구", "서구", "유성구", "중구"},
    "울산광역시": {"남구", "동구", "북구", "울주군", "중구"},
    "세종특별자치시": {"세종시"},
    "경기도": {"가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시", "남양주시",
             "동두천시", "부천시", "성남시", "수원시", "시흥시", "안산시", "안성시", "안양시", "양주시",
             "양평군", "여주시", "연천군", "오산시", "용인시", "의왕시", "의정부시", "이천시", "파주시",
             "평택시", "포천시", "하남시", "화성시"},
    "강원특별자치도": {"강릉시", "고성군", "동해시", "삼척시", "속초시", "양구군", "양양군", "영월군", "원주시",
                  "인제군", "정선군", "철원군", "춘천시", "태백시", "평창군", "홍천군", "화천군", "횡성군"},
    "충청북도": {"괴산군", "단양군", "보은군", "영동군", "옥천군", "음성군", "제천시", "증평군", "진천군", "청주시", "충주시"},
    "충청남도": {"계룡시", "공주시", "금산군", "논산시", "당진시", "보령시", "부여군", "서산시", "서천군",
             "아산시", "예산군", "천안시", "청양군", "태안군", "홍성군"},
    "전북특별자치도": {"고창군", "군산시", "김제시", "남원시", "무주군", "부안군", "순창군", "완주군",
                  "익산시", "임실군", "장수군", "전주시", "정읍시", "진안군"},
    "전라남도": {"강진군", "고흥군", "곡성군", "광양시", "구례군", "나주시", "담양군", "목포시", "무안군",
             "보성군", "순천시", "신안군", "여수시", "영광군", "영암군", "완도군", "장성군", "장흥군",
             "진도군", "함평군", "해남군", "화순군"},
    "경상북도": {"경산시", "경주시", "고령군", "구미시", "군위군", "김천시", "문경시", "봉화군", "상주시",
             "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "예천군", "울릉군", "울진군",
             "의성군", "청도군", "청송군", "칠곡군", "포항시"},
    "경상남도": {"거제시", "거창군", "고성군", "김해시", "남해군", "밀양시", "사천시", "산청군", "양산시",
             "의령군", "진주시", "창녕군", "창원시", "통영시", "하동군", "함안군", "함양군", "합천군"},
    "제주특별자치도": {"서귀포시", "제주시"}
}
# 메인 함수
async def generate_multiple_options(
    schedule_data: Dict[str, Any], 
    triple_api_service, 
    voice_input: str = ""  # 🔥 매개변수 추가
) -> Dict[str, Any]:
    """다중 옵션 생성 함수"""
    generator = MultipleOptionsGenerator(triple_api_service)
    return await generator.generate_options(schedule_data, voice_input)