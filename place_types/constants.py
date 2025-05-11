"""
장소 유형 관련 상수 및 상세 매핑 정보를 정의합니다.
Google Places API의 200개 이상 장소 유형을 내부 카테고리로 세분화하여 매핑합니다.
"""

# 장소 유형 대분류
CATEGORY_FOOD = "식음료"
CATEGORY_SHOPPING = "쇼핑"
CATEGORY_TRANSPORT = "교통"
CATEGORY_EDUCATION = "교육"
CATEGORY_ENTERTAINMENT = "엔터테인먼트"
CATEGORY_HEALTH = "건강"
CATEGORY_FINANCE = "금융"
CATEGORY_CULTURE = "문화"
CATEGORY_SPORTS = "스포츠"
CATEGORY_PUBLIC = "공공시설"
CATEGORY_NATURE = "자연"
CATEGORY_SERVICES = "서비스"
CATEGORY_LODGING = "숙박"
CATEGORY_AUTOMOTIVE = "자동차"
CATEGORY_RELIGIOUS = "종교시설"
CATEGORY_RESIDENTIAL = "주거시설"

# 기본 Google 유형 -> 내부 카테고리 매핑
DEFAULT_GOOGLE_TO_INTERNAL = {
    #####################################################
    # 식음료 카테고리 (Food & Beverage)
    #####################################################
    
    ## 식당 기본 유형
    "restaurant": f"{CATEGORY_FOOD},음식점",
    "food": f"{CATEGORY_FOOD},음식점",
    "meal_delivery": f"{CATEGORY_FOOD},음식점>배달",
    "meal_takeaway": f"{CATEGORY_FOOD},음식점>포장",
    
    ## 식당 특수 유형 - 서비스 기준
    "fine_dining_restaurant": f"{CATEGORY_FOOD},음식점>고급식당", 
    "buffet_restaurant": f"{CATEGORY_FOOD},음식점>뷔페",
    "food_court": f"{CATEGORY_FOOD},음식점>푸드코트",
    "breakfast_restaurant": f"{CATEGORY_FOOD},음식점>조식",
    "brunch_restaurant": f"{CATEGORY_FOOD},음식점>브런치",
    "lunch_restaurant": f"{CATEGORY_FOOD},음식점>점심",
    "dinner_restaurant": f"{CATEGORY_FOOD},음식점>저녁",
    "cafeteria": f"{CATEGORY_FOOD},음식점>구내식당",
    "diner": f"{CATEGORY_FOOD},음식점>다이너",
    
    ## 식당 특수 유형 - 요리 국가별
    "korean_restaurant": f"{CATEGORY_FOOD},음식점>한식",
    "japanese_restaurant": f"{CATEGORY_FOOD},음식점>일식",
    "chinese_restaurant": f"{CATEGORY_FOOD},음식점>중식",
    "vietnamese_restaurant": f"{CATEGORY_FOOD},음식점>베트남음식",
    "thai_restaurant": f"{CATEGORY_FOOD},음식점>태국음식", 
    "italian_restaurant": f"{CATEGORY_FOOD},음식점>이탈리안",
    "french_restaurant": f"{CATEGORY_FOOD},음식점>프렌치",
    "american_restaurant": f"{CATEGORY_FOOD},음식점>미국음식",
    "mexican_restaurant": f"{CATEGORY_FOOD},음식점>멕시칸",
    "mediterranean_restaurant": f"{CATEGORY_FOOD},음식점>지중해음식",
    "spanish_restaurant": f"{CATEGORY_FOOD},음식점>스페인음식",
    "greek_restaurant": f"{CATEGORY_FOOD},음식점>그리스음식",
    "turkish_restaurant": f"{CATEGORY_FOOD},음식점>터키음식",
    "middle_eastern_restaurant": f"{CATEGORY_FOOD},음식점>중동음식",
    "lebanese_restaurant": f"{CATEGORY_FOOD},음식점>레바논음식",
    "indian_restaurant": f"{CATEGORY_FOOD},음식점>인도음식",
    "indonesian_restaurant": f"{CATEGORY_FOOD},음식점>인도네시아음식",
    "brazilian_restaurant": f"{CATEGORY_FOOD},음식점>브라질음식",
    "african_restaurant": f"{CATEGORY_FOOD},음식점>아프리카음식",
    "afghani_restaurant": f"{CATEGORY_FOOD},음식점>아프가니스탄음식",
    
    ## 식당 특수 유형 - 요리 유형별
    "seafood_restaurant": f"{CATEGORY_FOOD},음식점>해산물",
    "steak_house": f"{CATEGORY_FOOD},음식점>스테이크",
    "barbecue_restaurant": f"{CATEGORY_FOOD},음식점>바베큐",
    "fast_food_restaurant": f"{CATEGORY_FOOD},음식점>패스트푸드",
    "hamburger_restaurant": f"{CATEGORY_FOOD},음식점>패스트푸드>햄버거",
    "pizza_restaurant": f"{CATEGORY_FOOD},음식점>패스트푸드>피자",
    "sandwich_shop": f"{CATEGORY_FOOD},음식점>패스트푸드>샌드위치",
    "ramen_restaurant": f"{CATEGORY_FOOD},음식점>라면",
    "sushi_restaurant": f"{CATEGORY_FOOD},음식점>스시",
    "bar_and_grill": f"{CATEGORY_FOOD},음식점>바앤그릴",
    
    ## 식당 특수 유형 - 식이 요구사항별
    "vegan_restaurant": f"{CATEGORY_FOOD},음식점>비건",
    "vegetarian_restaurant": f"{CATEGORY_FOOD},음식점>채식",
    "halal_restaurant": f"{CATEGORY_FOOD},음식점>할랄",
    "kosher_restaurant": f"{CATEGORY_FOOD},음식점>코셔",
    "gluten_free_restaurant": f"{CATEGORY_FOOD},음식점>글루텐프리",
    
    ## 카페 및 디저트
    "cafe": f"{CATEGORY_FOOD},카페",
    "coffee_shop": f"{CATEGORY_FOOD},카페>커피숍",
    "tea_house": f"{CATEGORY_FOOD},카페>티하우스",
    "bakery": f"{CATEGORY_FOOD},카페>베이커리",
    "dessert_restaurant": f"{CATEGORY_FOOD},카페>디저트",
    "dessert_shop": f"{CATEGORY_FOOD},카페>디저트",
    "ice_cream_shop": f"{CATEGORY_FOOD},카페>아이스크림",
    "juice_shop": f"{CATEGORY_FOOD},카페>주스바",
    "donut_shop": f"{CATEGORY_FOOD},카페>도넛",
    "candy_store": f"{CATEGORY_FOOD},카페>사탕",
    "chocolate_shop": f"{CATEGORY_FOOD},카페>초콜릿",
    "chocolate_factory": f"{CATEGORY_FOOD},카페>초콜릿",
    "confectionery": f"{CATEGORY_FOOD},카페>제과",
    "cat_cafe": f"{CATEGORY_FOOD},카페>고양이카페",
    "dog_cafe": f"{CATEGORY_FOOD},카페>애견카페",
    "internet_cafe": f"{CATEGORY_FOOD},카페>PC방",
    
    ## 주점
    "bar": f"{CATEGORY_FOOD},주점",
    "wine_bar": f"{CATEGORY_FOOD},주점>와인바",
    "pub": f"{CATEGORY_FOOD},주점>펍",
    "night_club": f"{CATEGORY_FOOD},주점>클럽",
    "karaoke": f"{CATEGORY_FOOD},주점>노래방",
    
    ## 식품 관련 매장
    "deli": f"{CATEGORY_FOOD},식품점>델리",
    "food_store": f"{CATEGORY_FOOD},식품점",
    "grocery_store": f"{CATEGORY_FOOD},식품점>식료품점",
    "butcher_shop": f"{CATEGORY_FOOD},식품점>정육점",
    "asian_grocery_store": f"{CATEGORY_FOOD},식품점>아시안식료품점",
    "bagel_shop": f"{CATEGORY_FOOD},식품점>베이글",
    "acai_shop": f"{CATEGORY_FOOD},식품점>아사이",
    
    ## 기타 식음료
    "food_delivery": f"{CATEGORY_FOOD},음식배달",
    
    #####################################################
    # 쇼핑 카테고리 (Shopping)
    #####################################################
    
    ## 대형 유통
    "shopping_mall": f"{CATEGORY_SHOPPING},쇼핑몰",
    "department_store": f"{CATEGORY_SHOPPING},백화점",
    "market": f"{CATEGORY_SHOPPING},시장",
    "supermarket": f"{CATEGORY_SHOPPING},슈퍼마켓",
    "convenience_store": f"{CATEGORY_SHOPPING},편의점",
    "warehouse_store": f"{CATEGORY_SHOPPING},창고형매장",
    "wholesale_store": f"{CATEGORY_SHOPPING},도매점",
    "discount_store": f"{CATEGORY_SHOPPING},할인점",
    "store": f"{CATEGORY_SHOPPING},상점",
    
    ## 의류 및 액세서리
    "clothing_store": f"{CATEGORY_SHOPPING},의류매장",
    "shoe_store": f"{CATEGORY_SHOPPING},신발매장",
    "jewelry_store": f"{CATEGORY_SHOPPING},보석상",
    "boutique": f"{CATEGORY_SHOPPING},부티크",
    "fashion_store": f"{CATEGORY_SHOPPING},패션매장",
    "accessories_store": f"{CATEGORY_SHOPPING},액세서리매장",
    
    ## 가전 및 가구
    "electronics_store": f"{CATEGORY_SHOPPING},전자제품매장",
    "computer_store": f"{CATEGORY_SHOPPING},컴퓨터매장",
    "cell_phone_store": f"{CATEGORY_SHOPPING},휴대폰매장",
    "furniture_store": f"{CATEGORY_SHOPPING},가구매장",
    "home_goods_store": f"{CATEGORY_SHOPPING},생활용품점",
    "home_improvement_store": f"{CATEGORY_SHOPPING},홈인테리어",
    "hardware_store": f"{CATEGORY_SHOPPING},철물점",
    "kitchen_supply_store": f"{CATEGORY_SHOPPING},주방용품점",
    "appliance_store": f"{CATEGORY_SHOPPING},가전제품점",
    
    ## 특수 상점
    "pet_store": f"{CATEGORY_SHOPPING},애완용품점",
    "book_store": f"{CATEGORY_SHOPPING},서점",
    "florist": f"{CATEGORY_SHOPPING},꽃집",
    "gift_shop": f"{CATEGORY_SHOPPING},선물가게",
    "stationery_store": f"{CATEGORY_SHOPPING},문구점",
    "toy_store": f"{CATEGORY_SHOPPING},장난감가게",
    "hobby_shop": f"{CATEGORY_SHOPPING},취미용품점",
    "sporting_goods_store": f"{CATEGORY_SHOPPING},스포츠용품점",
    "liquor_store": f"{CATEGORY_SHOPPING},주류판매점",
    "tobacco_shop": f"{CATEGORY_SHOPPING},담배판매점",
    "vape_shop": f"{CATEGORY_SHOPPING},전자담배매장",
    "video_game_store": f"{CATEGORY_SHOPPING},게임매장",
    "auto_parts_store": f"{CATEGORY_SHOPPING},자동차부품점",
    "bicycle_store": f"{CATEGORY_SHOPPING},자전거매장",
    "art_supply_store": f"{CATEGORY_SHOPPING},미술용품점",
    "music_store": f"{CATEGORY_SHOPPING},음악용품점",
    
    #####################################################
    # 교통 카테고리 (Transportation)
    #####################################################
    
    ## 대중교통
    "bus_station": f"{CATEGORY_TRANSPORT},버스정류장",
    "bus_stop": f"{CATEGORY_TRANSPORT},버스정류장",
    "subway_station": f"{CATEGORY_TRANSPORT},지하철역",
    "light_rail_station": f"{CATEGORY_TRANSPORT},경전철역",
    "train_station": f"{CATEGORY_TRANSPORT},기차역",
    "transit_station": f"{CATEGORY_TRANSPORT},대중교통역",
    "transit_depot": f"{CATEGORY_TRANSPORT},대중교통차고지",
    "tram_station": f"{CATEGORY_TRANSPORT},트램역",
    "ferry_terminal": f"{CATEGORY_TRANSPORT},페리터미널",
    
    ## 공항
    "airport": f"{CATEGORY_TRANSPORT},공항",
    "international_airport": f"{CATEGORY_TRANSPORT},국제공항",
    "domestic_airport": f"{CATEGORY_TRANSPORT},국내공항",
    "heliport": f"{CATEGORY_TRANSPORT},헬리포트",
    "airstrip": f"{CATEGORY_TRANSPORT},비행장",
    
    ## 주차 및 환승
    "parking": f"{CATEGORY_TRANSPORT},주차장",
    "parking_garage": f"{CATEGORY_TRANSPORT},주차빌딩",
    "park_and_ride": f"{CATEGORY_TRANSPORT},환승주차장",
    "taxi_stand": f"{CATEGORY_TRANSPORT},택시승강장",
    "car_rental": f"{CATEGORY_TRANSPORT},렌터카",
    "car_sharing": f"{CATEGORY_TRANSPORT},카셰어링",
    "bicycle_rental": f"{CATEGORY_TRANSPORT},자전거대여",
    
    ## 기타 교통
    "rest_stop": f"{CATEGORY_TRANSPORT},휴게소",
    "truck_stop": f"{CATEGORY_TRANSPORT},트럭휴게소",
    "electric_vehicle_charging_station": f"{CATEGORY_TRANSPORT},전기차충전소",
    "gas_station": f"{CATEGORY_TRANSPORT},주유소",
    
    #####################################################
    # 교육 카테고리 (Education)
    #####################################################
    
    ## 대학
    "university": f"{CATEGORY_EDUCATION},대학교",
    "college": f"{CATEGORY_EDUCATION},대학",
    "community_college": f"{CATEGORY_EDUCATION},전문대학",
    "technical_college": f"{CATEGORY_EDUCATION},기술대학",
    
    ## 학교
    "school": f"{CATEGORY_EDUCATION},학교",
    "primary_school": f"{CATEGORY_EDUCATION},학교>초등학교",
    "elementary_school": f"{CATEGORY_EDUCATION},학교>초등학교",
    "secondary_school": f"{CATEGORY_EDUCATION},학교>중고등학교",
    "middle_school": f"{CATEGORY_EDUCATION},학교>중학교",
    "high_school": f"{CATEGORY_EDUCATION},학교>고등학교",
    "private_school": f"{CATEGORY_EDUCATION},학교>사립학교",
    "public_school": f"{CATEGORY_EDUCATION},학교>공립학교",
    "international_school": f"{CATEGORY_EDUCATION},학교>국제학교",
    "alternative_school": f"{CATEGORY_EDUCATION},학교>대안학교",
    
    ## 특수 교육기관
    "preschool": f"{CATEGORY_EDUCATION},유치원",
    "kindergarten": f"{CATEGORY_EDUCATION},유치원",
    "language_school": f"{CATEGORY_EDUCATION},어학원",
    "driving_school": f"{CATEGORY_EDUCATION},운전학원",
    "music_school": f"{CATEGORY_EDUCATION},음악학원",
    "art_school": f"{CATEGORY_EDUCATION},미술학원",
    "cooking_school": f"{CATEGORY_EDUCATION},요리학원",
    "computer_training_center": f"{CATEGORY_EDUCATION},컴퓨터학원",
    "vocational_school": f"{CATEGORY_EDUCATION},직업학교",
    "boarding_school": f"{CATEGORY_EDUCATION},기숙학교",
    "special_education_school": f"{CATEGORY_EDUCATION},특수교육학교",
    "childcare_center": f"{CATEGORY_EDUCATION},보육원",
    
    ## 학습 관련 시설
    "library": f"{CATEGORY_EDUCATION},도서관",
    "research_center": f"{CATEGORY_EDUCATION},연구센터",
    "academic_institution": f"{CATEGORY_EDUCATION},학술기관",
    "study_center": f"{CATEGORY_EDUCATION},학습센터",
    "tutoring_center": f"{CATEGORY_EDUCATION},과외센터",
    "test_preparation_center": f"{CATEGORY_EDUCATION},시험준비센터",
    
    #####################################################
    # 엔터테인먼트 및 여가 (Entertainment & Leisure)
    #####################################################
    
    ## 영화/공연
    "movie_theater": f"{CATEGORY_ENTERTAINMENT},영화관",
    "movie_rental": f"{CATEGORY_ENTERTAINMENT},비디오대여점",
    "performing_arts_theater": f"{CATEGORY_ENTERTAINMENT},공연장",
    "concert_hall": f"{CATEGORY_ENTERTAINMENT},콘서트홀",
    "opera_house": f"{CATEGORY_ENTERTAINMENT},오페라하우스",
    "comedy_club": f"{CATEGORY_ENTERTAINMENT},코미디클럽",
    "theater": f"{CATEGORY_ENTERTAINMENT},극장",
    "amphitheater": f"{CATEGORY_ENTERTAINMENT},원형극장",
    "drive_in_theater": f"{CATEGORY_ENTERTAINMENT},자동차극장",
    "philharmonic_hall": f"{CATEGORY_ENTERTAINMENT},필하모닉홀",
    
    ## 놀이동산/게임
    "amusement_park": f"{CATEGORY_ENTERTAINMENT},놀이공원",
    "theme_park": f"{CATEGORY_ENTERTAINMENT},테마파크",
    "water_park": f"{CATEGORY_ENTERTAINMENT},워터파크",
    "amusement_center": f"{CATEGORY_ENTERTAINMENT},오락센터",
    "arcade": f"{CATEGORY_ENTERTAINMENT},오락실",
    "video_arcade": f"{CATEGORY_ENTERTAINMENT},비디오게임장",
    "bowling_alley": f"{CATEGORY_ENTERTAINMENT},볼링장",
    "roller_rink": f"{CATEGORY_ENTERTAINMENT},롤러장",
    "laser_tag": f"{CATEGORY_ENTERTAINMENT},레이저태그",
    "escape_room": f"{CATEGORY_ENTERTAINMENT},방탈출",
    "vr_center": f"{CATEGORY_ENTERTAINMENT},VR체험관",
    "casino": f"{CATEGORY_ENTERTAINMENT},카지노",
    "ferris_wheel": f"{CATEGORY_ENTERTAINMENT},대관람차",
    "roller_coaster": f"{CATEGORY_ENTERTAINMENT},롤러코스터",
    
    ## 문화시설
    "museum": f"{CATEGORY_CULTURE},박물관",
    "art_gallery": f"{CATEGORY_CULTURE},미술관",
    "art_studio": f"{CATEGORY_CULTURE},아트스튜디오",
    "exhibition_center": f"{CATEGORY_CULTURE},전시센터",
    "monument": f"{CATEGORY_CULTURE},기념물",
    "sculpture": f"{CATEGORY_CULTURE},조각상",
    "cultural_center": f"{CATEGORY_CULTURE},문화센터",
    "historical_landmark": f"{CATEGORY_CULTURE},역사적랜드마크",
    "historical_place": f"{CATEGORY_CULTURE},역사적장소",
    "cultural_landmark": f"{CATEGORY_CULTURE},문화랜드마크",
    "historical_museum": f"{CATEGORY_CULTURE},역사박물관",
    "science_museum": f"{CATEGORY_CULTURE},과학박물관",
    "children_museum": f"{CATEGORY_CULTURE},어린이박물관",
    "war_museum": f"{CATEGORY_CULTURE},전쟁박물관",
    "planetarium": f"{CATEGORY_CULTURE},천문대",
    "aquarium": f"{CATEGORY_CULTURE},수족관",
    
    ## 동물원/자연관찰
    "zoo": f"{CATEGORY_NATURE},동물원",
    "wildlife_park": f"{CATEGORY_NATURE},야생동물공원",
    "safari_park": f"{CATEGORY_NATURE},사파리파크",
    "bird_sanctuary": f"{CATEGORY_NATURE},조류보호구역",
    "wildlife_refuge": f"{CATEGORY_NATURE},야생동물보호구역",
    "botanical_garden": f"{CATEGORY_NATURE},식물원",
    
    ## 공원/레저
    "park": f"{CATEGORY_NATURE},공원",
    "national_park": f"{CATEGORY_NATURE},국립공원",
    "state_park": f"{CATEGORY_NATURE},주립공원",
    "city_park": f"{CATEGORY_NATURE},도시공원",
    "dog_park": f"{CATEGORY_NATURE},애견공원",
    "garden": f"{CATEGORY_NATURE},정원",
    "plaza": f"{CATEGORY_NATURE},광장",
    "playground": f"{CATEGORY_NATURE},놀이터",
    "picnic_ground": f"{CATEGORY_NATURE},피크닉장소",
    "camping_area": f"{CATEGORY_NATURE},캠핑장소",
    "barbecue_area": f"{CATEGORY_NATURE},바베큐장소",
    "observation_deck": f"{CATEGORY_NATURE},전망대",
    "scenic_overlook": f"{CATEGORY_NATURE},경치전망지",
    "visitor_center": f"{CATEGORY_NATURE},방문자센터",
    "tourist_attraction": f"{CATEGORY_NATURE},관광명소",
    
    ## 액티비티/스포츠
    "adventure_sports_center": f"{CATEGORY_SPORTS},모험스포츠센터",
    "cycling_park": f"{CATEGORY_SPORTS},자전거공원",
    "hiking_area": f"{CATEGORY_SPORTS},하이킹지역",
    "off_roading_area": f"{CATEGORY_SPORTS},오프로딩지역",
    "skateboard_park": f"{CATEGORY_SPORTS},스케이트보드공원",
    "sports_activity_location": f"{CATEGORY_SPORTS},스포츠활동장소",
    "marina": f"{CATEGORY_SPORTS},마리나",
    "fishing_area": f"{CATEGORY_SPORTS},낚시지역",
    "fishing_pond": f"{CATEGORY_SPORTS},낚시터",
    "fishing_charter": f"{CATEGORY_SPORTS},낚시전세",
    
    ## 기타 여가시설
    "dance_hall": f"{CATEGORY_ENTERTAINMENT},댄스홀",
    "banquet_hall": f"{CATEGORY_ENTERTAINMENT},연회장",
    "event_venue": f"{CATEGORY_ENTERTAINMENT},이벤트장소",
    "wedding_venue": f"{CATEGORY_ENTERTAINMENT},웨딩장소",
    "community_center": f"{CATEGORY_ENTERTAINMENT},커뮤니티센터",
    "senior_center": f"{CATEGORY_ENTERTAINMENT},노인센터",
    "youth_center": f"{CATEGORY_ENTERTAINMENT},청소년센터",
    "auditorium": f"{CATEGORY_ENTERTAINMENT},강당",
    "convention_center": f"{CATEGORY_ENTERTAINMENT},컨벤션센터",
    
    #####################################################
    # 스포츠 카테고리 (Sports)
    #####################################################
    
    ## 스포츠 시설
    "stadium": f"{CATEGORY_SPORTS},경기장",
    "arena": f"{CATEGORY_SPORTS},아레나",
    "sports_complex": f"{CATEGORY_SPORTS},스포츠컴플렉스",
    "athletic_field": f"{CATEGORY_SPORTS},운동장",
    "golf_course": f"{CATEGORY_SPORTS},골프장",
    "tennis_court": f"{CATEGORY_SPORTS},테니스코트",
    "basketball_court": f"{CATEGORY_SPORTS},농구코트",
    "baseball_field": f"{CATEGORY_SPORTS},야구장",
    "football_field": f"{CATEGORY_SPORTS},축구장",
    "ice_skating_rink": f"{CATEGORY_SPORTS},아이스스케이트장",
    "swimming_pool": f"{CATEGORY_SPORTS},수영장",
    "ski_resort": f"{CATEGORY_SPORTS},스키리조트",
    "race_track": f"{CATEGORY_SPORTS},경주트랙",
    "equestrian_center": f"{CATEGORY_SPORTS},승마센터",
    
    ## 피트니스 및 체육
    "gym": f"{CATEGORY_SPORTS},체육관",
    "fitness_center": f"{CATEGORY_SPORTS},피트니스센터",
    "sports_club": f"{CATEGORY_SPORTS},스포츠클럽",
    "boxing_gym": f"{CATEGORY_SPORTS},복싱체육관",
    "martial_arts_school": f"{CATEGORY_SPORTS},무술학원",
    "yoga_studio": f"{CATEGORY_HEALTH},요가스튜디오",
    "pilates_studio": f"{CATEGORY_HEALTH},필라테스스튜디오",
    "dance_studio": f"{CATEGORY_SPORTS},댄스스튜디오",
    "sports_coaching": f"{CATEGORY_SPORTS},스포츠코칭",
    
    #####################################################
    # 건강 및 웰니스 (Health & Wellness)
    #####################################################
    
    ## 병원 및 진료소
    "hospital": f"{CATEGORY_HEALTH},병원",
    "clinic": f"{CATEGORY_HEALTH},의원",
    "medical_center": f"{CATEGORY_HEALTH},의료센터",
    "emergency_room": f"{CATEGORY_HEALTH},응급실",
    "urgent_care": f"{CATEGORY_HEALTH},긴급의료",
    "doctor": f"{CATEGORY_HEALTH},의사",
    "general_practitioner": f"{CATEGORY_HEALTH},일반의",
    
    ## 전문 의료
    "dentist": f"{CATEGORY_HEALTH},치과",
    "dental_clinic": f"{CATEGORY_HEALTH},치과의원",
    "orthodontist": f"{CATEGORY_HEALTH},치아교정과",
    "ophthalmologist": f"{CATEGORY_HEALTH},안과",
    "optometrist": f"{CATEGORY_HEALTH},검안사",
    "pediatrician": f"{CATEGORY_HEALTH},소아과",
    "dermatologist": f"{CATEGORY_HEALTH},피부과",
    "orthopedist": f"{CATEGORY_HEALTH},정형외과",
    "plastic_surgeon": f"{CATEGORY_HEALTH},성형외과",
    "gynecologist": f"{CATEGORY_HEALTH},산부인과",
    "obstetrician": f"{CATEGORY_HEALTH},산과",
    "cardiologist": f"{CATEGORY_HEALTH},심장내과",
    "neurologist": f"{CATEGORY_HEALTH},신경과",
    "psychiatrist": f"{CATEGORY_HEALTH},정신과",
    "psychologist": f"{CATEGORY_HEALTH},심리상담사",
    "therapist": f"{CATEGORY_HEALTH},치료사",
    
    ## 대체의학 및 기타 의료
    "chiropractor": f"{CATEGORY_HEALTH},척추지압사",
    "physical_therapist": f"{CATEGORY_HEALTH},물리치료사",
    "physiotherapist": f"{CATEGORY_HEALTH},물리치료사",
    "acupuncturist": f"{CATEGORY_HEALTH},침술사",
    "massage": f"{CATEGORY_HEALTH},마사지",
    "massage_therapist": f"{CATEGORY_HEALTH},마사지치료사",
    "nutrition_center": f"{CATEGORY_HEALTH},영양센터",
    "dietitian": f"{CATEGORY_HEALTH},영양사",
    "foot_care": f"{CATEGORY_HEALTH},발관리",
    "hearing_aid_store": f"{CATEGORY_HEALTH},보청기판매점",
    
    ## 의료 검사 및 실험
    "medical_lab": f"{CATEGORY_HEALTH},의료검사실",
    "diagnostic_center": f"{CATEGORY_HEALTH},진단센터",
    "blood_bank": f"{CATEGORY_HEALTH},혈액은행",
    "dialysis_center": f"{CATEGORY_HEALTH},투석센터",
    "rehab_center": f"{CATEGORY_HEALTH},재활센터",
    
    ## 약국 및 의료용품
    "pharmacy": f"{CATEGORY_HEALTH},약국",
    "drugstore": f"{CATEGORY_HEALTH},드럭스토어",
    "medical_supply_store": f"{CATEGORY_HEALTH},의료용품점",
    
    ## 웰니스 및 스파
    "spa": f"{CATEGORY_HEALTH},스파",
    "wellness_center": f"{CATEGORY_HEALTH},웰니스센터",
    "sauna": f"{CATEGORY_HEALTH},사우나",
    "hot_spring": f"{CATEGORY_HEALTH},온천",
    "tanning_studio": f"{CATEGORY_HEALTH},태닝스튜디오",
    "beauty_salon": f"{CATEGORY_HEALTH},미용실",
    "hair_salon": f"{CATEGORY_HEALTH},미용실",
    "hair_care": f"{CATEGORY_HEALTH},헤어케어",
    "barber_shop": f"{CATEGORY_HEALTH},이발소",
    "nail_salon": f"{CATEGORY_HEALTH},네일샵",
    "skin_care_clinic": f"{CATEGORY_HEALTH},피부관리실",
    
#####################################################
    # 금융 카테고리 (Finance)
    #####################################################
    
    ## 은행 및 ATM
    "bank": f"{CATEGORY_FINANCE},은행",
    "atm": f"{CATEGORY_FINANCE},ATM",
    "credit_union": f"{CATEGORY_FINANCE},신용조합",
    "investment_bank": f"{CATEGORY_FINANCE},투자은행",
    "community_bank": f"{CATEGORY_FINANCE},지역은행",
    "private_bank": f"{CATEGORY_FINANCE},사설은행",
    "mobile_bank": f"{CATEGORY_FINANCE},모바일뱅킹",
    
    ## 금융 서비스
    "finance": f"{CATEGORY_FINANCE},금융",
    "investment_firm": f"{CATEGORY_FINANCE},투자회사",
    "financial_advisor": f"{CATEGORY_FINANCE},재정자문",
    "accounting": f"{CATEGORY_FINANCE},회계",
    "tax_service": f"{CATEGORY_FINANCE},세무서비스",
    "insurance_agency": f"{CATEGORY_FINANCE},보험대리점",
    "money_transfer": f"{CATEGORY_FINANCE},송금서비스",
    "currency_exchange": f"{CATEGORY_FINANCE},환전소",
    "pawn_shop": f"{CATEGORY_FINANCE},전당포",
    "check_cashing_service": f"{CATEGORY_FINANCE},수표현금화서비스",
    "brokerage": f"{CATEGORY_FINANCE},중개업",
    "stock_exchange": f"{CATEGORY_FINANCE},증권거래소",
    "loan_agency": f"{CATEGORY_FINANCE},대출기관",
    "mortgage_broker": f"{CATEGORY_FINANCE},주택담보대출중개인",
    "stock_broker": f"{CATEGORY_FINANCE},주식중개인",
    
    #####################################################
    # 정부 기관 (Government)
    #####################################################
    
    ## 행정 기관
    "government_office": f"{CATEGORY_PUBLIC},관공서",
    "city_hall": f"{CATEGORY_PUBLIC},시청",
    "town_hall": f"{CATEGORY_PUBLIC},군청",
    "village_hall": f"{CATEGORY_PUBLIC},면사무소",
    "courthouse": f"{CATEGORY_PUBLIC},법원",
    "embassy": f"{CATEGORY_PUBLIC},대사관",
    "consulate": f"{CATEGORY_PUBLIC},영사관",
    "local_government_office": f"{CATEGORY_PUBLIC},지방행정기관",
    "tax_office": f"{CATEGORY_PUBLIC},세무서",
    "passport_office": f"{CATEGORY_PUBLIC},여권사무소",
    "visa_office": f"{CATEGORY_PUBLIC},비자사무소",
    "registry_office": f"{CATEGORY_PUBLIC},등록사무소",
    "public_service_center": f"{CATEGORY_PUBLIC},민원센터",
    
    ## 우편 및 공공서비스
    "post_office": f"{CATEGORY_PUBLIC},우체국",
    "postal_service": f"{CATEGORY_PUBLIC},우편서비스",
    "public_utility": f"{CATEGORY_PUBLIC},공공시설",
    "water_utility": f"{CATEGORY_PUBLIC},수도시설",
    "electric_utility": f"{CATEGORY_PUBLIC},전기시설",
    "gas_utility": f"{CATEGORY_PUBLIC},가스시설",
    "recycling_center": f"{CATEGORY_PUBLIC},재활용센터",
    "waste_management": f"{CATEGORY_PUBLIC},폐기물관리",
    
    ## 응급 서비스
    "fire_station": f"{CATEGORY_PUBLIC},소방서",
    "police": f"{CATEGORY_PUBLIC},경찰서",
    "police_station": f"{CATEGORY_PUBLIC},경찰서",
    "neighborhood_police_station": f"{CATEGORY_PUBLIC},파출소",
    "emergency_service": f"{CATEGORY_PUBLIC},응급서비스",
    "ambulance_service": f"{CATEGORY_PUBLIC},구급대",
    "civil_defense": f"{CATEGORY_PUBLIC},민방위",
    "coast_guard": f"{CATEGORY_PUBLIC},해안경비대",
    
    ## 군사 시설
    "military_base": f"{CATEGORY_PUBLIC},군부대",
    "military_office": f"{CATEGORY_PUBLIC},군사무소",
    "naval_base": f"{CATEGORY_PUBLIC},해군기지",
    "air_force_base": f"{CATEGORY_PUBLIC},공군기지",
    "army_base": f"{CATEGORY_PUBLIC},육군기지",
    
    ## 기타 공공시설
    "public_bath": f"{CATEGORY_PUBLIC},공중목욕탕",
    "public_bathroom": f"{CATEGORY_PUBLIC},공중화장실",
    "public_phone": f"{CATEGORY_PUBLIC},공중전화",
    "public_service": f"{CATEGORY_PUBLIC},공공서비스",
    "public_information_center": f"{CATEGORY_PUBLIC},공공정보센터",
    
    #####################################################
    # 숙박 카테고리 (Lodging)
    #####################################################
    
    ## 호텔
    "lodging": f"{CATEGORY_LODGING},숙박",
    "hotel": f"{CATEGORY_LODGING},호텔",
    "resort_hotel": f"{CATEGORY_LODGING},리조트호텔",
    "motel": f"{CATEGORY_LODGING},모텔",
    "inn": f"{CATEGORY_LODGING},여관",
    "extended_stay_hotel": f"{CATEGORY_LODGING},장기체류호텔",
    "boutique_hotel": f"{CATEGORY_LODGING},부티크호텔",
    "apartment_hotel": f"{CATEGORY_LODGING},아파트형호텔",
    "suite_hotel": f"{CATEGORY_LODGING},스위트호텔",
    "luxury_hotel": f"{CATEGORY_LODGING},럭셔리호텔",
    "budget_hotel": f"{CATEGORY_LODGING},저가호텔",
    
    ## 기타 숙박시설
    "hostel": f"{CATEGORY_LODGING},호스텔",
    "guest_house": f"{CATEGORY_LODGING},게스트하우스",
    "bed_and_breakfast": f"{CATEGORY_LODGING},B&B",
    "cottage": f"{CATEGORY_LODGING},별장",
    "villa": f"{CATEGORY_LODGING},빌라",
    "cabin": f"{CATEGORY_LODGING},오두막",
    "camping_cabin": f"{CATEGORY_LODGING},캠핑캐빈",
    "campground": f"{CATEGORY_LODGING},캠핑장",
    "rv_park": f"{CATEGORY_LODGING},RV파크",
    "private_guest_room": f"{CATEGORY_LODGING},개인객실",
    "farmstay": f"{CATEGORY_LODGING},농장체험숙박",
    "japanese_inn": f"{CATEGORY_LODGING},료칸",
    "budget_japanese_inn": f"{CATEGORY_LODGING},민슈쿠",
    
    #####################################################
    # 자동차 카테고리 (Automotive)
    #####################################################
    
    ## 자동차 판매 및 대여
    "car_dealer": f"{CATEGORY_AUTOMOTIVE},자동차딜러",
    "car_dealership": f"{CATEGORY_AUTOMOTIVE},자동차대리점",
    "used_car_dealer": f"{CATEGORY_AUTOMOTIVE},중고차딜러",
    "car_rental": f"{CATEGORY_AUTOMOTIVE},렌터카",
    "truck_rental": f"{CATEGORY_AUTOMOTIVE},트럭렌탈",
    "rv_rental": f"{CATEGORY_AUTOMOTIVE},RV렌탈",
    "motorcycle_dealer": f"{CATEGORY_AUTOMOTIVE},오토바이딜러",
    "boat_dealer": f"{CATEGORY_AUTOMOTIVE},보트딜러",
    
    ## 자동차 서비스
    "car_repair": f"{CATEGORY_AUTOMOTIVE},자동차수리",
    "auto_repair": f"{CATEGORY_AUTOMOTIVE},자동차수리",
    "car_wash": f"{CATEGORY_AUTOMOTIVE},세차장",
    "auto_detailing": f"{CATEGORY_AUTOMOTIVE},자동차디테일링",
    "oil_change_station": f"{CATEGORY_AUTOMOTIVE},오일교체소",
    "auto_body_shop": f"{CATEGORY_AUTOMOTIVE},자동차판금도장",
    "tire_shop": f"{CATEGORY_AUTOMOTIVE},타이어점",
    "smog_check_station": f"{CATEGORY_AUTOMOTIVE},매연검사소",
    "car_inspection": f"{CATEGORY_AUTOMOTIVE},자동차검사소",
    "towing_service": f"{CATEGORY_AUTOMOTIVE},견인서비스",
    "auto_glass_shop": f"{CATEGORY_AUTOMOTIVE},자동차유리점",
    "auto_electrical_service": f"{CATEGORY_AUTOMOTIVE},자동차전기서비스",
    "car_alarm_installer": f"{CATEGORY_AUTOMOTIVE},자동차경보기설치",
    "car_audio_installer": f"{CATEGORY_AUTOMOTIVE},자동차오디오설치",
    "car_upholstery": f"{CATEGORY_AUTOMOTIVE},자동차내장재",
    
    #####################################################
    # 종교 시설 (Religious Places)
    #####################################################
    
    ## 종교 시설
    "place_of_worship": f"{CATEGORY_RELIGIOUS},종교시설",
    "church": f"{CATEGORY_RELIGIOUS},교회",
    "cathedral": f"{CATEGORY_RELIGIOUS},대성당",
    "chapel": f"{CATEGORY_RELIGIOUS},예배당",
    "mosque": f"{CATEGORY_RELIGIOUS},모스크",
    "synagogue": f"{CATEGORY_RELIGIOUS},유대교회당",
    "hindu_temple": f"{CATEGORY_RELIGIOUS},힌두사원",
    "buddhist_temple": f"{CATEGORY_RELIGIOUS},불교사원",
    "temple": f"{CATEGORY_RELIGIOUS},사원",
    "monastery": f"{CATEGORY_RELIGIOUS},수도원",
    "shrine": f"{CATEGORY_RELIGIOUS},신사",
    "mission": f"{CATEGORY_RELIGIOUS},선교소",
    "convent": f"{CATEGORY_RELIGIOUS},수녀원",
    "religious_center": f"{CATEGORY_RELIGIOUS},종교센터",
    "parish_hall": f"{CATEGORY_RELIGIOUS},교구회관",
    
    #####################################################
    # 주거 시설 (Residential)
    #####################################################
    
    ## 주거 시설
    "housing_complex": f"{CATEGORY_RESIDENTIAL},주택단지",
    "apartment_complex": f"{CATEGORY_RESIDENTIAL},아파트단지",
    "apartment_building": f"{CATEGORY_RESIDENTIAL},아파트",
    "condominium_complex": f"{CATEGORY_RESIDENTIAL},콘도미니엄",
    "residential_complex": f"{CATEGORY_RESIDENTIAL},주거단지",
    "gated_community": f"{CATEGORY_RESIDENTIAL},통제주거지역",
    "mobile_home_park": f"{CATEGORY_RESIDENTIAL},이동식주택단지",
    "senior_housing": f"{CATEGORY_RESIDENTIAL},노인주택",
    "retirement_community": f"{CATEGORY_RESIDENTIAL},은퇴자커뮤니티",
    "assisted_living_facility": f"{CATEGORY_RESIDENTIAL},생활보조시설",
    "dormitory": f"{CATEGORY_RESIDENTIAL},기숙사",
    "housing_development": f"{CATEGORY_RESIDENTIAL},주택개발",
    "single_family_home": f"{CATEGORY_RESIDENTIAL},단독주택",
    "townhouse": f"{CATEGORY_RESIDENTIAL},타운하우스",
    "duplex": f"{CATEGORY_RESIDENTIAL},듀플렉스",
    "triplex": f"{CATEGORY_RESIDENTIAL},트리플렉스",
    
    #####################################################
    # 서비스 카테고리 (Services)
    #####################################################
    
    ## 전문 서비스
    "lawyer": f"{CATEGORY_SERVICES},변호사",
    "law_firm": f"{CATEGORY_SERVICES},법률사무소",
    "notary": f"{CATEGORY_SERVICES},공증사",
    "real_estate_agency": f"{CATEGORY_SERVICES},부동산중개소",
    "real_estate_appraiser": f"{CATEGORY_SERVICES},부동산감정사",
    "marketing_agency": f"{CATEGORY_SERVICES},마케팅회사",
    "advertising_agency": f"{CATEGORY_SERVICES},광고회사",
    "public_relations": f"{CATEGORY_SERVICES},홍보회사",
    "consulting_agency": f"{CATEGORY_SERVICES},컨설팅회사",
    "employment_agency": f"{CATEGORY_SERVICES},취업알선소",
    "security_service": f"{CATEGORY_SERVICES},보안서비스",
    "private_investigator": f"{CATEGORY_SERVICES},사설탐정",
    "architect": f"{CATEGORY_SERVICES},건축가",
    "engineering_firm": f"{CATEGORY_SERVICES},엔지니어링회사",
    "surveyor": f"{CATEGORY_SERVICES},측량사",
    "graphic_designer": f"{CATEGORY_SERVICES},그래픽디자이너",
    "interior_designer": f"{CATEGORY_SERVICES},인테리어디자이너",
    "home_inspector": f"{CATEGORY_SERVICES},주택검사관",
    "event_planner": f"{CATEGORY_SERVICES},이벤트플래너",
    "wedding_planner": f"{CATEGORY_SERVICES},웨딩플래너",
    "consultant": f"{CATEGORY_SERVICES},컨설턴트",
    "translator": f"{CATEGORY_SERVICES},번역사",
    "interpreter": f"{CATEGORY_SERVICES},통역사",
    "photographer": f"{CATEGORY_SERVICES},사진작가",
    "videographer": f"{CATEGORY_SERVICES},비디오작가",
    
    ## 기타 서비스
    "courier_service": f"{CATEGORY_SERVICES},택배서비스",
    "postal_service": f"{CATEGORY_SERVICES},우편서비스",
    "shipping_company": f"{CATEGORY_SERVICES},운송회사",
    "moving_company": f"{CATEGORY_SERVICES},이사업체",
    "storage": f"{CATEGORY_SERVICES},보관소",
    "self_storage": f"{CATEGORY_SERVICES},셀프스토리지",
    "printing_service": f"{CATEGORY_SERVICES},인쇄서비스",
    "copy_shop": f"{CATEGORY_SERVICES},복사점",
    "cleaning_service": f"{CATEGORY_SERVICES},청소서비스",
    "laundry": f"{CATEGORY_SERVICES},세탁소",
    "dry_cleaner": f"{CATEGORY_SERVICES},드라이클리닝",
    "tailor": f"{CATEGORY_SERVICES},재봉사",
    "shoe_repair": f"{CATEGORY_SERVICES},구두수선",
    "locksmith": f"{CATEGORY_SERVICES},열쇠공",
    "funeral_home": f"{CATEGORY_SERVICES},장례식장",
    "crematorium": f"{CATEGORY_SERVICES},화장장",
    "cemetery": f"{CATEGORY_SERVICES},묘지",
    "mortuary": f"{CATEGORY_SERVICES},영안실",
    "pest_control": f"{CATEGORY_SERVICES},해충방제",
    
    ## 기술/서비스 전문가
    "contractor": f"{CATEGORY_SERVICES},도급업자",
    "general_contractor": f"{CATEGORY_SERVICES},종합도급업자",
    "electrician": f"{CATEGORY_SERVICES},전기공",
    "plumber": f"{CATEGORY_SERVICES},배관공",
    "hvac_contractor": f"{CATEGORY_SERVICES},냉난방시공자",
    "roofer": f"{CATEGORY_SERVICES},지붕공",
    "carpenter": f"{CATEGORY_SERVICES},목수",
    "painter": f"{CATEGORY_SERVICES},페인트공",
    "handyman": f"{CATEGORY_SERVICES},수리공",
    "mason": f"{CATEGORY_SERVICES},석공",
    "landscaper": f"{CATEGORY_SERVICES},조경사",
    "gardener": f"{CATEGORY_SERVICES},정원사",
    "tree_service": f"{CATEGORY_SERVICES},나무관리",
    "pool_service": f"{CATEGORY_SERVICES},수영장관리",
    "appliance_repair": f"{CATEGORY_SERVICES},가전수리",
    "computer_repair": f"{CATEGORY_SERVICES},컴퓨터수리",
    "phone_repair": f"{CATEGORY_SERVICES},전화기수리",
    "flooring_contractor": f"{CATEGORY_SERVICES},바닥재시공자",
    "insulation_contractor": f"{CATEGORY_SERVICES},단열재시공자",
    "roofing_contractor": f"{CATEGORY_SERVICES},지붕시공자",
    "fence_contractor": f"{CATEGORY_SERVICES},울타리시공자",
    "deck_contractor": f"{CATEGORY_SERVICES},데크시공자",
    "cabinet_maker": f"{CATEGORY_SERVICES},가구제작자",
    
    ## 여행 관련 서비스
    "travel_agency": f"{CATEGORY_SERVICES},여행사",
    "tour_agency": f"{CATEGORY_SERVICES},관광여행사",
    "tourist_information_center": f"{CATEGORY_SERVICES},관광안내소",
    "visa_consultant": f"{CATEGORY_SERVICES},비자상담소",
    "guide_service": f"{CATEGORY_SERVICES},가이드서비스",
    "airport_shuttle": f"{CATEGORY_SERVICES},공항셔틀",
    
    ## 개인 케어
    "beautician": f"{CATEGORY_SERVICES},미용사",
    "makeup_artist": f"{CATEGORY_SERVICES},메이크업아티스트",
    "body_art_service": f"{CATEGORY_SERVICES},바디아트",
    "tattoo_shop": f"{CATEGORY_SERVICES},타투샵",
    "piercing_shop": f"{CATEGORY_SERVICES},피어싱샵",
    "child_care_agency": f"{CATEGORY_SERVICES},어린이돌봄서비스",
    "babysitter": f"{CATEGORY_SERVICES},아이돌보미",
    "caregiver": f"{CATEGORY_SERVICES},간병인",
    "elder_care": f"{CATEGORY_SERVICES},노인돌봄",
    
    ## 기타
    "catering_service": f"{CATEGORY_SERVICES},케이터링서비스",
    "telecommunications_service_provider": f"{CATEGORY_SERVICES},통신서비스",
    "internet_service_provider": f"{CATEGORY_SERVICES},인터넷서비스",
    "internet_cafe": f"{CATEGORY_SERVICES},인터넷카페",
    "photocopier": f"{CATEGORY_SERVICES},복사업체",
    "dog_walker": f"{CATEGORY_SERVICES},개산책서비스",
    "dog_groomer": f"{CATEGORY_SERVICES},애견미용사",
    "pet_trainer": f"{CATEGORY_SERVICES},반려동물훈련사",
    "pet_sitter": f"{CATEGORY_SERVICES},반려동물돌보미",
    "pet_boarding": f"{CATEGORY_SERVICES},반려동물숙박",
    "psychic": f"{CATEGORY_SERVICES},심령술사",
    "fortune_teller": f"{CATEGORY_SERVICES},점집",
    "astrologer": f"{CATEGORY_SERVICES},점성술사",
    "veterinary_care": f"{CATEGORY_SERVICES},수의사",
    "animal_hospital": f"{CATEGORY_SERVICES},동물병원",
    "summer_camp_organizer": f"{CATEGORY_SERVICES},여름캠프주최자",
    "children_camp": f"{CATEGORY_SERVICES},어린이캠프",
    
    #####################################################
    # 자연 지형 카테고리 (Natural Features)
    #####################################################
    
    ## 자연 지형
    "natural_feature": f"{CATEGORY_NATURE},자연지형",
    "mountain": f"{CATEGORY_NATURE},산",
    "hill": f"{CATEGORY_NATURE},언덕",
    "valley": f"{CATEGORY_NATURE},계곡",
    "canyon": f"{CATEGORY_NATURE},협곡",
    "plateau": f"{CATEGORY_NATURE},고원",
    "desert": f"{CATEGORY_NATURE},사막",
    "forest": f"{CATEGORY_NATURE},숲",
    "jungle": f"{CATEGORY_NATURE},정글",
    "swamp": f"{CATEGORY_NATURE},늪지",
    "wetland": f"{CATEGORY_NATURE},습지",
    "grassland": f"{CATEGORY_NATURE},초원",
    "prairie": f"{CATEGORY_NATURE},대초원",
    "tundra": f"{CATEGORY_NATURE},툰드라",
    "glacier": f"{CATEGORY_NATURE},빙하",
    "volcano": f"{CATEGORY_NATURE},화산",
    "geyser": f"{CATEGORY_NATURE},간헐천",
    "hot_spring": f"{CATEGORY_NATURE},온천",
    "waterfall": f"{CATEGORY_NATURE},폭포",
    "lake": f"{CATEGORY_NATURE},호수",
    "pond": f"{CATEGORY_NATURE},연못",
    "river": f"{CATEGORY_NATURE},강",
    "stream": f"{CATEGORY_NATURE},개울",
    "creek": f"{CATEGORY_NATURE},시내",
    "beach": f"{CATEGORY_NATURE},해변",
    "bay": f"{CATEGORY_NATURE},만",
    "gulf": f"{CATEGORY_NATURE},걸프",
    "strait": f"{CATEGORY_NATURE},해협",
    "channel": f"{CATEGORY_NATURE},수로",
    "island": f"{CATEGORY_NATURE},섬",
    "archipelago": f"{CATEGORY_NATURE},군도",
    "peninsula": f"{CATEGORY_NATURE},반도",
    "reef": f"{CATEGORY_NATURE},암초",
    "coastal_feature": f"{CATEGORY_NATURE},해안지형",
    "cave": f"{CATEGORY_NATURE},동굴",
    
    #####################################################
    # 기타 일반 유형 (General Types)
    #####################################################
    
    ## 일반적인 분류
    "point_of_interest": "관심장소",
    "establishment": "시설물",
    "premise": "구내",
    "landmark": "랜드마크",
    "geocode": "지오코드",
    "route": "도로",
    "health": "건강",
    "political": "정치적구역",
    "subpremise": "하위구내",
    "colloquial_area": "구어적지역",
    "continent": "대륙",
    "plus_code": "플러스코드",
    "street_address": "도로명주소",
    "postal_code": "우편번호",
    "stable": "마구간",
    "town_square": "광장",
    
    ## 행정구역
    "administrative_area_level_1": "광역시도",
    "administrative_area_level_2": "시군구",
    "administrative_area_level_3": "읍면동",
    "administrative_area_level_4": "법정동",
    "administrative_area_level_5": "행정동",
    "administrative_area_level_6": "하위행정구역",
    "administrative_area_level_7": "최하위행정구역",
    "locality": "지역",
    "sublocality": "하위지역",
    "sublocality_level_1": "하위지역레벨1",
    "sublocality_level_2": "하위지역레벨2",
    "sublocality_level_3": "하위지역레벨3",
    "sublocality_level_4": "하위지역레벨4",
    "sublocality_level_5": "하위지역레벨5",
    "neighborhood": "동네",
    "country": "국가",
    "postal_town": "우편지역",
    "postal_code_prefix": "우편번호접두어",
    "postal_code_suffix": "우편번호접미어",
    "school_district": "학군",
    
    ## 기타
    "general_contractor": "종합건설업자",
    "food": "음식",
    "store": "가게",
    "intersection": "교차로",
    "transit_station": "대중교통역",
    "floor": "층",
    "room": "방",
    "finance": "금융",
}

# 내부 카테고리 -> Google 유형 매핑
# 주요 카테고리만 먼저 정의하고, 나머지는 실제 구현 시 추가
DEFAULT_INTERNAL_TO_GOOGLE = {
    #####################################################
    # 식음료 카테고리 매핑
    #####################################################
    
    # 카페 관련
    "카페": ["cafe", "coffee_shop", "tea_house"],
    "커피숍": ["coffee_shop", "cafe"],
    "티하우스": ["tea_house", "cafe"],
    "베이커리": ["bakery"],
    "디저트": ["dessert_restaurant", "dessert_shop", "cafe"],
    "아이스크림": ["ice_cream_shop"],
    "주스바": ["juice_shop"],
    "제과": ["confectionery", "bakery"],
    
    # 식당 관련
    "음식점": ["restaurant", "food"],
    "고급식당": ["fine_dining_restaurant", "restaurant"],
    "뷔페": ["buffet_restaurant", "restaurant"],
    "푸드코트": ["food_court"],
    "한식": ["korean_restaurant", "restaurant"],
    "일식": ["japanese_restaurant", "restaurant"],
    "중식": ["chinese_restaurant", "restaurant"],
    "양식": ["american_restaurant", "italian_restaurant", "french_restaurant", "restaurant"],
    "이탈리안": ["italian_restaurant", "restaurant"],
    "멕시칸": ["mexican_restaurant", "restaurant"],
    "태국음식": ["thai_restaurant", "restaurant"],
    "인도음식": ["indian_restaurant", "restaurant"],
    "해산물": ["seafood_restaurant", "restaurant"],
    "스테이크": ["steak_house", "restaurant"],
    "바베큐": ["barbecue_restaurant", "restaurant"],
    "패스트푸드": ["fast_food_restaurant", "hamburger_restaurant", "pizza_restaurant", "meal_takeaway"],
    "햄버거": ["hamburger_restaurant", "fast_food_restaurant"],
    "피자": ["pizza_restaurant", "fast_food_restaurant"],
    "샌드위치": ["sandwich_shop", "fast_food_restaurant"],
    "라면": ["ramen_restaurant", "restaurant"],
    "스시": ["sushi_restaurant", "japanese_restaurant", "restaurant"],
    "비건": ["vegan_restaurant", "vegetarian_restaurant", "restaurant"],
    "채식": ["vegetarian_restaurant", "vegan_restaurant", "restaurant"],
    
    # 주점 관련
    "주점": ["bar", "wine_bar", "pub", "night_club"],
    "와인바": ["wine_bar", "bar"],
    "펍": ["pub", "bar"],
    "클럽": ["night_club"],
    "노래방": ["karaoke"],
    
    #####################################################
    # 쇼핑 카테고리 매핑
    #####################################################
    
    "쇼핑몰": ["shopping_mall"],
    "백화점": ["department_store"],
    "시장": ["market"],
    "슈퍼마켓": ["supermarket", "grocery_store"],
    "편의점": ["convenience_store"],
    "의류매장": ["clothing_store"],
    "신발매장": ["shoe_store"],
    "보석상": ["jewelry_store"],
    "전자제품매장": ["electronics_store"],
    "휴대폰매장": ["cell_phone_store"],
    "가구매장": ["furniture_store"],
    "생활용품점": ["home_goods_store"],
    "철물점": ["hardware_store"],
    "애완용품점": ["pet_store"],
    "서점": ["book_store"],
    "꽃집": ["florist"],
    "선물가게": ["gift_shop"],
    "문구점": ["stationery_store"],
    "장난감가게": ["toy_store"],
    "스포츠용품점": ["sporting_goods_store"],
    "주류판매점": ["liquor_store"],
    
    #####################################################
    # 교통 카테고리 매핑
    #####################################################
    
    "버스정류장": ["bus_station", "bus_stop"],
    "지하철역": ["subway_station", "transit_station"],
    "기차역": ["train_station", "transit_station"],
    "공항": ["airport", "international_airport"],
    "주차장": ["parking"],
    "렌터카": ["car_rental"],
    "택시승강장": ["taxi_stand"],
    "휴게소": ["rest_stop"],
    "주유소": ["gas_station"],
    "전기차충전소": ["electric_vehicle_charging_station"],
    
    #####################################################
    # 교육 카테고리 매핑
    #####################################################
    
    "대학교": ["university", "college"],
    "학교": ["school", "primary_school", "secondary_school"],
    "초등학교": ["primary_school", "elementary_school", "school"],
    "중학교": ["middle_school", "secondary_school", "school"],
    "고등학교": ["high_school", "secondary_school", "school"],
    "유치원": ["preschool", "kindergarten"],
    "학원": ["language_school", "art_school", "music_school"],
    "도서관": ["library"],
    
    #####################################################
    # 엔터테인먼트 및 문화 카테고리 매핑
    #####################################################
    
    "영화관": ["movie_theater"],
    "공연장": ["performing_arts_theater", "concert_hall"],
    "콘서트홀": ["concert_hall"],
    "극장": ["theater"],
    "놀이공원": ["amusement_park", "theme_park"],
    "워터파크": ["water_park", "amusement_park"],
    "오락실": ["arcade", "video_arcade", "amusement_center"],
    "볼링장": ["bowling_alley"],
    "스케이트장": ["ice_skating_rink"],
    "카지노": ["casino"],
    
    "박물관": ["museum"],
    "미술관": ["art_gallery", "museum"],
    "전시관": ["exhibition_center", "art_gallery"],
    "역사적장소": ["historical_place", "historical_landmark"],
    "기념물": ["monument"],
    "천문대": ["planetarium"],
    "수족관": ["aquarium"],
    
    #####################################################
    # 자연 및 공원 카테고리 매핑
    #####################################################
    
    "공원": ["park", "city_park"],
    "국립공원": ["national_park", "park"],
    "정원": ["garden", "botanical_garden"],
    "식물원": ["botanical_garden"],
    "동물원": ["zoo"],
    "야생동물공원": ["wildlife_park"],
    "해변": ["beach"],
    "피크닉장소": ["picnic_ground"],
    "캠핑장소": ["camping_area", "campground"],
    "전망대": ["observation_deck", "scenic_overlook"],
    "산": ["mountain", "natural_feature"],
    "호수": ["lake", "natural_feature"],
    "강": ["river", "natural_feature"],
    "폭포": ["waterfall", "natural_feature"],
    "온천": ["hot_spring"],
    
    #####################################################
    # 스포츠 카테고리 매핑
    #####################################################
    
    "경기장": ["stadium", "arena", "sports_complex"],
    "체육관": ["gym", "fitness_center", "sports_complex"],
    "피트니스센터": ["fitness_center", "gym"],
    "스포츠클럽": ["sports_club"],
    "골프장": ["golf_course"],
    "수영장": ["swimming_pool"],
    "테니스코트": ["tennis_court"],
    "농구코트": ["basketball_court"],
    "축구장": ["football_field", "athletic_field"],
    "야구장": ["baseball_field", "athletic_field"],
    "스키장": ["ski_resort"],
    
    #####################################################
    # 건강 카테고리 매핑
    #####################################################
    
    "병원": ["hospital"],
    "의원": ["clinic", "doctor"],
    "의료센터": ["medical_center"],
    "응급실": ["emergency_room"],
    "치과": ["dentist", "dental_clinic"],
    "안과": ["ophthalmologist", "optometrist"],
    "소아과": ["pediatrician"],
    "피부과": ["dermatologist"],
    "정형외과": ["orthopedist"],
    "산부인과": ["gynecologist", "obstetrician"],
    "정신과": ["psychiatrist"],
    "물리치료사": ["physiotherapist", "physical_therapist"],
    "약국": ["pharmacy"],
    "드럭스토어": ["drugstore"],
    
    "스파": ["spa"],
    "웰니스센터": ["wellness_center"],
    "요가스튜디오": ["yoga_studio"],
    "필라테스스튜디오": ["pilates_studio"],
    "마사지": ["massage"],
    "사우나": ["sauna"],
    "미용실": ["beauty_salon", "hair_salon"],
    "이발소": ["barber_shop"],
    "네일샵": ["nail_salon"],
    "피부관리실": ["skin_care_clinic"],
    
    #####################################################
    # 금융 카테고리 매핑
    #####################################################
    
    "은행": ["bank"],
    "ATM": ["atm"],
    "보험대리점": ["insurance_agency"],
    "회계": ["accounting"],
    "부동산중개소": ["real_estate_agency"],
    "보험회사": ["insurance_agency"],
    "대출기관": ["loan_agency"],
    "투자회사": ["investment_firm"],
    
    #####################################################
    # 정부 및 공공시설 카테고리 매핑
    #####################################################
    
    "관공서": ["government_office", "local_government_office"],
    "시청": ["city_hall"],
    "군청": ["town_hall"],
    "법원": ["courthouse"],
    "대사관": ["embassy"],
    "영사관": ["consulate"],
    "우체국": ["post_office"],
    "소방서": ["fire_station"],
    "경찰서": ["police", "police_station"],
    "파출소": ["neighborhood_police_station"],
    "공중화장실": ["public_bathroom"],
    
    #####################################################
    # 숙박 카테고리 매핑
    #####################################################
    
    "호텔": ["hotel", "lodging"],
    "모텔": ["motel", "lodging"],
    "리조트": ["resort_hotel", "lodging"],
    "여관": ["inn", "lodging"],
    "게스트하우스": ["guest_house", "lodging"],
    "호스텔": ["hostel", "lodging"],
    "B&B": ["bed_and_breakfast", "lodging"],
    "캠핑장": ["campground", "rv_park"],
    
    #####################################################
    # 자동차 카테고리 매핑
    #####################################################
    
    "자동차딜러": ["car_dealer", "car_dealership"],
    "중고차딜러": ["used_car_dealer", "car_dealer"],
    "자동차수리": ["car_repair", "auto_repair"],
    "세차장": ["car_wash"],
    "타이어점": ["tire_shop"],
    
    #####################################################
    # 종교 시설 카테고리 매핑
    #####################################################
    
    "종교시설": ["place_of_worship"],
    "교회": ["church", "place_of_worship"],
    "성당": ["cathedral", "church", "place_of_worship"],
    "모스크": ["mosque", "place_of_worship"],
    "사원": ["temple", "hindu_temple", "buddhist_temple", "place_of_worship"],
    "불교사원": ["buddhist_temple", "temple", "place_of_worship"],
    
    #####################################################
    # 서비스 카테고리 매핑
    #####################################################
    
    "변호사": ["lawyer", "law_firm"],
    "법률사무소": ["law_firm"],
    "부동산": ["real_estate_agency"],
    "보안서비스": ["security_service"],
    "청소서비스": ["cleaning_service"],
    "이사업체": ["moving_company"],
    "세탁소": ["laundry", "dry_cleaner"],
    "미용사": ["beautician", "beauty_salon"],
    "재봉사": ["tailor"],
    "열쇠공": ["locksmith"],
    "장례식장": ["funeral_home"],
    "수리공": ["handyman", "electrician", "plumber"],
    "전기공": ["electrician"],
    "배관공": ["plumber"],
    "여행사": ["travel_agency"],
    "관광안내소": ["tourist_information_center"],
    "수의사": ["veterinary_care", "animal_hospital"],
    
    #####################################################
    # 행정 지역 매핑
    #####################################################
    
    "광역시도": ["administrative_area_level_1"],
    "시군구": ["administrative_area_level_2"],
    "읍면동": ["administrative_area_level_3", "sublocality_level_1"],
    "지역": ["locality"],
    "동네": ["neighborhood"],
    "국가": ["country"],
    
    #####################################################
    # 기타 일반 매핑
    #####################################################
    
    "관심장소": ["point_of_interest"],
    "시설물": ["establishment"],
    "랜드마크": ["landmark"],
}

# 유형 우선순위 정의
# 숫자가 높을수록 우선순위가 높음 (0-100 범위)
TYPE_PRIORITY = {
    #####################################################
    # 식음료 카테고리 우선순위
    #####################################################
    
    # 음식점 세부 유형 - 높은 우선순위
    "korean_restaurant": 95,
    "japanese_restaurant": 95,
    "chinese_restaurant": 95,
    "italian_restaurant": 95,
    "french_restaurant": 95,
    "american_restaurant": 95, 
    "mexican_restaurant": 95,
    "thai_restaurant": 95,
    "indian_restaurant": 95,
    "vietnamese_restaurant": 95,
    "seafood_restaurant": 95,
    "steak_house": 95,
    "ramen_restaurant": 95,
    "sushi_restaurant": 95,
    "barbecue_restaurant": 95,
    "vegan_restaurant": 95,
    "vegetarian_restaurant": 95,
    
    # 음식점 일반 유형 - 중간 우선순위
    "restaurant": 80,
    "fine_dining_restaurant": 90,
    "buffet_restaurant": 90,
    "food_court": 85,
    "bar_and_grill": 85,
    
    # 음식점 형태 유형 - 낮은 우선순위
    "meal_delivery": 75,
    "meal_takeaway": 75,
    "food": 60,
    
    # 패스트푸드 세부 유형 - 높은 우선순위
    "hamburger_restaurant": 95,
    "pizza_restaurant": 95,
    "sandwich_shop": 95,
    
    # 패스트푸드 일반 유형 - 중간 우선순위
    "fast_food_restaurant": 85,
    
    # 카페 세부 유형 - 높은 우선순위
    "coffee_shop": 95,
    "tea_house": 95,
    "bakery": 95,
    "dessert_restaurant": 95,
    "dessert_shop": 95,
    "ice_cream_shop": 95,
    "juice_shop": 95,
    "cat_cafe": 95,
    "dog_cafe": 95,
    
    # 카페 일반 유형 - 중간 우선순위
    "cafe": 80,
    
    # 주점 세부 유형 - 높은 우선순위
    "wine_bar": 95,
    "pub": 95,
    
    # 주점 일반 유형 - 중간 우선순위
    "bar": 80,
    "night_club": 80,
    
    #####################################################
    # 쇼핑 카테고리 우선순위
    #####################################################
    
    # 쇼핑 중심지 - 높은 우선순위
    "shopping_mall": 90,
    "department_store": 90,
    
    # 식품 상점 - 높은 우선순위
    "supermarket": 90,
    "grocery_store": 90,
    "convenience_store": 90,
    "liquor_store": 90,
    
    # 전문 상점 - 높은 우선순위
    "clothing_store": 90,
    "shoe_store": 90,
    "jewelry_store": 90,
    "electronics_store": 90,
    "cell_phone_store": 90,
    "furniture_store": 90,
    "home_goods_store": 90,
    "hardware_store": 90,
    "pet_store": 90,
    "book_store": 90,
    "sporting_goods_store": 90,
    
    # 일반 상점 - 중간 우선순위
    "store": 70,
    
    #####################################################
    # 교통 카테고리 우선순위
    #####################################################
    
    # 주요 교통시설 - 높은 우선순위
    "subway_station": 95,
    "train_station": 95,
    "airport": 95,
    "international_airport": 95,
    
    # 버스정류장 - 중간 우선순위
    "bus_station": 85,
    "bus_stop": 85,
    
    # 기타 교통 관련 - 중간 우선순위
    "parking": 80,
    "gas_station": 80,
    "car_rental": 80,
    "electric_vehicle_charging_station": 80,
    
    #####################################################
    # 교육 카테고리 우선순위
    #####################################################
    
    # 학교 - 높은 우선순위
    "university": 95,
    "school": 90,
    "primary_school": 95,
    "secondary_school": 95,
    "library": 90,
    
    #####################################################
    # 엔터테인먼트 카테고리 우선순위
    #####################################################
    
    # 엔터테인먼트 - 높은 우선순위
    "movie_theater": 95,
    "performing_arts_theater": 95,
    "concert_hall": 95,
    "amusement_park": 95,
    "theme_park": 95,
    "water_park": 95,
    "museum": 95,
    "art_gallery": 95,
    "zoo": 95,
    "aquarium": 95,
    
    # 스포츠 시설 - 높은 우선순위
    "stadium": 95,
    "arena": 95,
    "sports_complex": 95,
    "golf_course": 95,
    "bowling_alley": 95,
    "fitness_center": 95,
    "gym": 95,
    "swimming_pool": 95,
    
    #####################################################
    # 자연 카테고리 우선순위
    #####################################################
    
    # 자연 - 높은 우선순위
    "park": 90,
    "national_park": 95,
    "beach": 95,
    "garden": 90,
    "botanical_garden": 95,
    
    # 자연 지형 - 중간 우선순위
    "natural_feature": 80,
    
    #####################################################
    # 건강 카테고리 우선순위
    #####################################################
    
    # 의료시설 - 높은 우선순위
    "hospital": 95,
    "doctor": 95,
    "dentist": 95,
    "pharmacy": 95,
    
    # 웰빙 - 높은 우선순위
    "spa": 95,
    "beauty_salon": 90,
    "hair_salon": 90,
    
    #####################################################
    # 정부 및 공공시설 카테고리 우선순위
    #####################################################
    
    # 정부 기관 - 높은 우선순위
    "city_hall": 95,
    "post_office": 95,
    "police_station": 95,
    "fire_station": 95,
    
    # 일반 정부 - 중간 우선순위
    "government_office": 90,
    "local_government_office": 90,
    
    #####################################################
    # 숙박 카테고리 우선순위
    #####################################################
    
    # 숙박시설 - 높은 우선순위
    "hotel": 95,
    "resort_hotel": 95,
    "motel": 95,
    
    # 일반 숙박 - 중간 우선순위
    "lodging": 85,
    
    #####################################################
    # 종교 카테고리 우선순위
    #####################################################
    
    # 종교시설 특정 - 높은 우선순위
    "church": 95,
    "mosque": 95,
    "hindu_temple": 95,
    "buddhist_temple": 95,
    
    # 일반 종교 - 중간 우선순위
    "place_of_worship": 85,
    
    #####################################################
    # 기타 일반 유형 우선순위
    #####################################################
    
    # 일반 유형 - 낮은 우선순위 (가장 일반적)
    "point_of_interest": 10,
    "establishment": 5,
    "premise": 8,
    "geocode": 3,
    "political": 2,
    "route": 7,
}

# 음성 키워드와 Google 장소 유형 매핑
# 음성 입력에서 특정 키워드가 발견되면 적용할 필터링 규칙
VOICE_KEYWORD_TO_TYPES = {
    #####################################################
    # 식음료 관련 키워드
    #####################################################
    
    # 카페 관련 키워드
    "카페": {
        "includedTypes": ["cafe", "coffee_shop", "tea_house", "bakery", "dessert_restaurant", "dessert_shop"],
        "excludedTypes": ["restaurant", "fast_food_restaurant", "meal_takeaway", "bar"]
    },
    "커피": {
        "includedTypes": ["cafe", "coffee_shop"],
        "excludedTypes": ["restaurant", "fast_food_restaurant"]
    },
    "커피숍": {
        "includedTypes": ["coffee_shop", "cafe"],
        "excludedTypes": ["restaurant", "fast_food_restaurant"]
    },
    "디저트": {
        "includedTypes": ["dessert_restaurant", "dessert_shop", "cafe", "bakery", "ice_cream_shop"],
        "excludedTypes": ["restaurant", "meal_takeaway"]
    },
    "베이커리": {
        "includedTypes": ["bakery"],
        "excludedTypes": ["restaurant"]
    },
    "제과": {
        "includedTypes": ["bakery", "confectionery"],
        "excludedTypes": ["restaurant"]
    },
    "케이크": {
        "includedTypes": ["bakery", "dessert_shop", "dessert_restaurant"],
        "excludedTypes": ["restaurant"]
    },
    "아이스크림": {
        "includedTypes": ["ice_cream_shop", "dessert_shop"],
        "excludedTypes": ["restaurant"]
    },
    
    # 식당 관련 키워드
    "식당": {
        "includedTypes": ["restaurant", "korean_restaurant", "japanese_restaurant", "chinese_restaurant"],
        "excludedTypes": ["cafe", "fast_food_restaurant"]
    },
    "음식점": {
        "includedTypes": ["restaurant", "korean_restaurant", "japanese_restaurant", "chinese_restaurant"],
        "excludedTypes": ["cafe"]
    },
    "맛집": {
        "includedTypes": ["restaurant", "korean_restaurant", "japanese_restaurant", "chinese_restaurant"],
        "excludedTypes": ["cafe", "fast_food_restaurant"]
    },
    "레스토랑": {
        "includedTypes": ["restaurant", "fine_dining_restaurant"],
        "excludedTypes": ["cafe", "fast_food_restaurant"]
    },
    "한식": {
        "includedTypes": ["korean_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "일식": {
        "includedTypes": ["japanese_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "중식": {
        "includedTypes": ["chinese_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "양식": {
        "includedTypes": ["italian_restaurant", "french_restaurant", "american_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "이탈리안": {
        "includedTypes": ["italian_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "프렌치": {
        "includedTypes": ["french_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "태국": {
        "includedTypes": ["thai_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "인도": {
        "includedTypes": ["indian_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "멕시칸": {
        "includedTypes": ["mexican_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "해산물": {
        "includedTypes": ["seafood_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "스테이크": {
        "includedTypes": ["steak_house", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "비건": {
        "includedTypes": ["vegan_restaurant", "vegetarian_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "채식": {
        "includedTypes": ["vegetarian_restaurant", "vegan_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    
    # 패스트푸드 관련 키워드
    "패스트푸드": {
        "includedTypes": ["fast_food_restaurant", "hamburger_restaurant", "pizza_restaurant", "meal_takeaway"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "햄버거": {
        "includedTypes": ["hamburger_restaurant", "fast_food_restaurant"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "피자": {
        "includedTypes": ["pizza_restaurant", "fast_food_restaurant"],
        "excludedTypes": ["cafe"]
    },
    "치킨": {
        "includedTypes": ["fast_food_restaurant", "restaurant"],
        "excludedTypes": ["cafe"]
    },
    "샌드위치": {
        "includedTypes": ["sandwich_shop", "fast_food_restaurant"],
        "excludedTypes": ["cafe"]
    },
    
    # 주점 관련 키워드
    "주점": {
        "includedTypes": ["bar", "wine_bar", "pub"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "술집": {
        "includedTypes": ["bar", "pub"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "바": {
        "includedTypes": ["bar", "wine_bar"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "와인바": {
        "includedTypes": ["wine_bar", "bar"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "펍": {
        "includedTypes": ["pub", "bar"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "노래방": {
        "includedTypes": ["karaoke", "night_club"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "클럽": {
        "includedTypes": ["night_club"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 쇼핑 관련 키워드
    #####################################################
    
    "쇼핑몰": {
        "includedTypes": ["shopping_mall"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "백화점": {
        "includedTypes": ["department_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "마트": {
        "includedTypes": ["supermarket", "grocery_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "슈퍼마켓": {
        "includedTypes": ["supermarket", "grocery_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "편의점": {
        "includedTypes": ["convenience_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "의류": {
        "includedTypes": ["clothing_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "신발": {
        "includedTypes": ["shoe_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "전자제품": {
        "includedTypes": ["electronics_store", "cell_phone_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "가구": {
        "includedTypes": ["furniture_store", "home_goods_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "서점": {
        "includedTypes": ["book_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "꽃집": {
        "includedTypes": ["florist"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "애완동물": {
        "includedTypes": ["pet_store"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 문화/엔터테인먼트 관련 키워드
    #####################################################
    
    "영화관": {
        "includedTypes": ["movie_theater"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "공연장": {
        "includedTypes": ["performing_arts_theater", "concert_hall"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "박물관": {
        "includedTypes": ["museum"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "미술관": {
        "includedTypes": ["art_gallery", "museum"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "놀이공원": {
        "includedTypes": ["amusement_park", "theme_park"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "워터파크": {
        "includedTypes": ["water_park"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "동물원": {
        "includedTypes": ["zoo"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "수족관": {
        "includedTypes": ["aquarium"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "볼링장": {
        "includedTypes": ["bowling_alley"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 자연/공원 관련 키워드
    #####################################################
    
    "공원": {
        "includedTypes": ["park", "city_park", "national_park", "state_park"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "정원": {
        "includedTypes": ["garden", "botanical_garden"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "식물원": {
        "includedTypes": ["botanical_garden"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "해변": {
        "includedTypes": ["beach"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 스포츠 관련 키워드
    #####################################################
    
    "경기장": {
        "includedTypes": ["stadium", "arena", "sports_complex"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "체육관": {
        "includedTypes": ["gym", "fitness_center", "sports_complex"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "헬스장": {
        "includedTypes": ["fitness_center", "gym"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "수영장": {
        "includedTypes": ["swimming_pool"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "골프장": {
        "includedTypes": ["golf_course"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "스키장": {
        "includedTypes": ["ski_resort"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 교통 관련 키워드
    #####################################################
    
    "지하철역": {
        "includedTypes": ["subway_station", "transit_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "버스정류장": {
        "includedTypes": ["bus_station", "bus_stop"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "기차역": {
        "includedTypes": ["train_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "공항": {
        "includedTypes": ["airport", "international_airport"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "주차장": {
        "includedTypes": ["parking"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "주유소": {
        "includedTypes": ["gas_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "충전소": {
        "includedTypes": ["electric_vehicle_charging_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 교육 관련 키워드
    #####################################################
    
    "대학": {
        "includedTypes": ["university", "college"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "학교": {
        "includedTypes": ["school", "primary_school", "secondary_school"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "도서관": {
        "includedTypes": ["library"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "미술학원": {
        "includedTypes": ["art_school"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "음악학원": {
        "includedTypes": ["music_school"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 의료/건강 관련 키워드
    #####################################################
    
    "병원": {
        "includedTypes": ["hospital", "doctor", "medical_center"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "치과": {
        "includedTypes": ["dentist", "dental_clinic"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "약국": {
        "includedTypes": ["pharmacy", "drugstore"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "안과": {
        "includedTypes": ["ophthalmologist", "optometrist"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "피부과": {
        "includedTypes": ["dermatologist"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "정형외과": {
        "includedTypes": ["orthopedist"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "정신과": {
        "includedTypes": ["psychiatrist", "psychologist"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "스파": {
        "includedTypes": ["spa", "wellness_center"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "마사지": {
        "includedTypes": ["massage", "spa"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "요가": {
        "includedTypes": ["yoga_studio"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "필라테스": {
        "includedTypes": ["pilates_studio"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "미용실": {
        "includedTypes": ["beauty_salon", "hair_salon"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "이발소": {
        "includedTypes": ["barber_shop"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "네일샵": {
        "includedTypes": ["nail_salon"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 금융 관련 키워드
    #####################################################
    
    "은행": {
        "includedTypes": ["bank"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "ATM": {
        "includedTypes": ["atm"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "보험": {
        "includedTypes": ["insurance_agency"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "부동산": {
        "includedTypes": ["real_estate_agency"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 정부/공공시설 관련 키워드
    #####################################################
    
    "시청": {
        "includedTypes": ["city_hall", "local_government_office"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "법원": {
        "includedTypes": ["courthouse"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "경찰서": {
        "includedTypes": ["police", "police_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "소방서": {
        "includedTypes": ["fire_station"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "우체국": {
        "includedTypes": ["post_office"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "관공서": {
        "includedTypes": ["government_office", "local_government_office"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 숙박 관련 키워드
    #####################################################
    
    "호텔": {
        "includedTypes": ["hotel", "resort_hotel", "lodging"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "모텔": {
        "includedTypes": ["motel", "lodging"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "리조트": {
        "includedTypes": ["resort_hotel", "lodging"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "게스트하우스": {
        "includedTypes": ["guest_house", "lodging"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "캠핑장": {
        "includedTypes": ["campground", "rv_park"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 자동차 관련 키워드
    #####################################################
    
    "자동차": {
        "includedTypes": ["car_dealer", "car_repair", "car_wash"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "정비소": {
        "includedTypes": ["car_repair", "auto_repair"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "세차장": {
        "includedTypes": ["car_wash"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "중고차": {
        "includedTypes": ["used_car_dealer", "car_dealer"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 종교 관련 키워드
    #####################################################
    
    "교회": {
        "includedTypes": ["church", "place_of_worship"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "성당": {
        "includedTypes": ["church", "cathedral", "place_of_worship"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "절": {
        "includedTypes": ["buddhist_temple", "temple", "place_of_worship"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "사원": {
        "includedTypes": ["temple", "hindu_temple", "buddhist_temple", "place_of_worship"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 서비스 관련 키워드
    #####################################################
    
    "세탁소": {
        "includedTypes": ["laundry", "dry_cleaner"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "수리": {
        "includedTypes": ["handyman", "electrician", "plumber"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "이사": {
        "includedTypes": ["moving_company"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "보관소": {
        "includedTypes": ["storage", "self_storage"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "여행사": {
        "includedTypes": ["travel_agency"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    "동물병원": {
        "includedTypes": ["veterinary_care", "animal_hospital"],
        "excludedTypes": ["cafe", "restaurant"]
    },
    
    #####################################################
    # 복합 키워드 (여러 유형 고려)
    #####################################################
    
    # 식사 관련 포괄적 키워드
    "먹을곳": {
        "includedTypes": ["restaurant", "cafe", "bakery", "fast_food_restaurant"],
        "excludedTypes": []
    },
    "식사": {
        "includedTypes": ["restaurant", "korean_restaurant", "japanese_restaurant", "chinese_restaurant"],
        "excludedTypes": []
    },
    "간식": {
        "includedTypes": ["cafe", "bakery", "dessert_restaurant", "dessert_shop", "fast_food_restaurant"],
        "excludedTypes": []
    },
    
    # 휴식 관련 포괄적 키워드
    "휴식": {
        "includedTypes": ["park", "cafe", "spa", "library"],
        "excludedTypes": []
    },
    "힐링": {
        "includedTypes": ["spa", "park", "garden", "wellness_center"],
        "excludedTypes": []
    },
    
    # 쇼핑 관련 포괄적 키워드
    "쇼핑": {
        "includedTypes": ["shopping_mall", "department_store", "clothing_store", "shoe_store"],
        "excludedTypes": []
    },
    "구매": {
        "includedTypes": ["shopping_mall", "department_store", "supermarket", "store"],
        "excludedTypes": []
    },
    
    # 여가 관련 포괄적 키워드
    "여가": {
        "includedTypes": ["park", "movie_theater", "amusement_park", "museum", "art_gallery"],
        "excludedTypes": []
    },
    "나들이": {
        "includedTypes": ["park", "zoo", "museum", "beach", "amusement_park"],
        "excludedTypes": []
    },
    "구경": {
        "includedTypes": ["museum", "art_gallery", "shopping_mall", "tourist_attraction"],
        "excludedTypes": []
    },
    
    # 레저 관련 포괄적 키워드
    "레저": {
        "includedTypes": ["sports_complex", "amusement_park", "water_park", "bowling_alley"],
        "excludedTypes": []
    },
    "스포츠": {
        "includedTypes": ["sports_complex", "stadium", "fitness_center", "gym"],
        "excludedTypes": []
    },
    "운동": {
        "includedTypes": ["fitness_center", "gym", "sports_complex", "swimming_pool"],
        "excludedTypes": []
    },
    
    # 주변 시설 키워드
    "주변": {
        "includedTypes": ["restaurant", "cafe", "convenience_store", "bank", "pharmacy"],
        "excludedTypes": []
    },
    "근처": {
        "includedTypes": ["restaurant", "cafe", "convenience_store", "bank", "pharmacy"],
        "excludedTypes": []
    },
    
    # 긴급 서비스 키워드
    "긴급": {
        "includedTypes": ["hospital", "police", "fire_station", "pharmacy"],
        "excludedTypes": []
    },
    "응급": {
        "includedTypes": ["hospital", "emergency_room", "pharmacy"],
        "excludedTypes": []
    },
    
    # 계절별 선호 장소
    "여름": {
        "includedTypes": ["beach", "water_park", "swimming_pool", "ice_cream_shop"],
        "excludedTypes": []
    },
    "겨울": {
        "includedTypes": ["ski_resort", "shopping_mall", "movie_theater", "cafe"],
        "excludedTypes": []
    },
    
    # 날씨 관련 선호 장소
    "비": {
        "includedTypes": ["shopping_mall", "movie_theater", "museum", "cafe"],
        "excludedTypes": ["park", "beach", "amusement_park"]
    },
    "맑음": {
        "includedTypes": ["park", "beach", "amusement_park", "zoo"],
        "excludedTypes": []
    },
    
    # 시간대별 선호 장소
    "아침": {
        "includedTypes": ["cafe", "park", "bakery", "breakfast_restaurant"],
        "excludedTypes": ["night_club", "bar"]
    },
    "점심": {
        "includedTypes": ["restaurant", "korean_restaurant", "japanese_restaurant", "fast_food_restaurant"],
        "excludedTypes": ["night_club"]
    },
    "저녁": {
        "includedTypes": ["restaurant", "bar", "movie_theater", "korean_restaurant"],
        "excludedTypes": []
    },
    "밤": {
        "includedTypes": ["bar", "night_club", "restaurant", "cafe", "movie_theater"],
        "excludedTypes": []
    },
    
    # 연령대별 선호 장소
    "아이": {
        "includedTypes": ["amusement_park", "zoo", "aquarium", "ice_cream_shop", "playground"],
        "excludedTypes": ["bar", "night_club"]
    },
    "어린이": {
        "includedTypes": ["amusement_park", "zoo", "aquarium", "ice_cream_shop", "playground"],
        "excludedTypes": ["bar", "night_club"]
    },
    "청소년": {
        "includedTypes": ["movie_theater", "arcade", "cafe", "shopping_mall"],
        "excludedTypes": ["bar", "night_club"]
    },
    "어른": {
        "includedTypes": ["restaurant", "cafe", "museum", "shopping_mall"],
        "excludedTypes": []
    },
    "노인": {
        "includedTypes": ["park", "restaurant", "pharmacy", "hospital", "senior_center"],
        "excludedTypes": []
    },
    
    # 기타 특수 키워드
    "데이트": {
        "includedTypes": ["cafe", "restaurant", "movie_theater", "park"],
        "excludedTypes": []
    },
    "기념일": {
        "includedTypes": ["fine_dining_restaurant", "restaurant", "cafe", "hotel"],
        "excludedTypes": []
    },
    "회의": {
        "includedTypes": ["cafe", "restaurant", "hotel", "conference_room"],
        "excludedTypes": []
    },
    "인터넷": {
        "includedTypes": ["cafe", "internet_cafe", "library"],
        "excludedTypes": []
    },
    "공부": {
        "includedTypes": ["cafe", "library", "book_store"],
        "excludedTypes": ["bar", "night_club"]
    },
    "독서": {
        "includedTypes": ["library", "book_store", "cafe"],
        "excludedTypes": []
    },
    "작업": {
        "includedTypes": ["cafe", "library", "coworking_space"],
        "excludedTypes": []
    },
    "미팅": {
        "includedTypes": ["cafe", "restaurant", "hotel"],
        "excludedTypes": []
    },
    "파티": {
        "includedTypes": ["bar", "restaurant", "night_club", "event_venue"],
        "excludedTypes": []
    },
}

# 시간대별 장소 유형 매핑
TIME_OF_DAY_TO_TYPES = {
    "morning": {
        "includedTypes": ["cafe", "bakery", "breakfast_restaurant"],
        "excludedTypes": ["bar", "night_club"]
    },
    "afternoon": {
        "includedTypes": ["restaurant", "cafe", "shopping_mall", "park"],
        "excludedTypes": ["night_club"]
    },
    "evening": {
        "includedTypes": ["restaurant", "movie_theater", "bar"],
        "excludedTypes": []
    },
    "night": {
        "includedTypes": ["bar", "night_club", "restaurant"],
        "excludedTypes": []
    }
}

# 날씨별 장소 유형 매핑
WEATHER_TO_TYPES = {
    "sunny": {
        "includedTypes": ["park", "beach", "amusement_park"],
        "excludedTypes": []
    },
    "rainy": {
        "includedTypes": ["shopping_mall", "movie_theater", "museum", "cafe"],
        "excludedTypes": ["park", "beach", "amusement_park"]
    },
    "cold": {
        "includedTypes": ["shopping_mall", "movie_theater", "museum", "cafe", "restaurant"],
        "excludedTypes": ["beach", "water_park"]
    },
    "hot": {
        "includedTypes": ["swimming_pool", "water_park", "ice_cream_shop", "beach"],
        "excludedTypes": []
    }
}

# 이동 방식별 장소 유형 매핑
TRANSPORTATION_TO_TYPES = {
    "walk": {
        "radius": 1000,  # 도보 검색 반경 (미터)
        "includedTypes": ["restaurant", "cafe", "convenience_store", "pharmacy"],
        "excludedTypes": []
    },
    "bike": {
        "radius": 3000,  # 자전거 검색 반경 (미터)
        "includedTypes": ["restaurant", "cafe", "park", "shopping_mall"],
        "excludedTypes": []
    },
    "public_transit": {
        "radius": 10000,  # 대중교통 검색 반경 (미터)
        "includedTypes": ["restaurant", "shopping_mall", "museum", "amusement_park"],
        "excludedTypes": []
    },
    "car": {
        "radius": 30000,  # 자동차 검색 반경 (미터)
        "includedTypes": ["restaurant", "shopping_mall", "amusement_park", "national_park"],
        "excludedTypes": []
    }
}