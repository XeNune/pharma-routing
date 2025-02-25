from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
import itertools
import time as t
import random

app = FastAPI()
templates = Jinja2Templates(directory="templates")

GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "http://overpass-api.de/api/interpreter"
OSRM_TABLE_URL = "https://routing.openstreetmap.de/routed-foot/table/v1/foot/"
OSRM_ROUTE_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/foot/"

HEADERS = {"User-Agent": "jija"}


def get_coordinates(address):
    """Геокодинг адреса с помощью Nominatim."""
    t.sleep(1)  # Ограничение API Nominatim (1 запрос в секунду)
    params = {"q": address, "format": "json"} # Параметры запроса
    try:
        response = requests.get(GEOCODER_URL, params=params, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        # Возвращаем координаты (широта, долгота), если данные получены
        return (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
    except requests.exceptions.RequestException:
        return None

def build_initial_route(hospital_coords, home_coords):
    """
    Построение начального(прямого) маршрута между больницей и домом с использованием OSRM API.
    """
    # Формируем строку координат для запроса к OSRM
    route_coords = f"{hospital_coords[1]},{hospital_coords[0]};{home_coords[1]},{home_coords[0]}"
    # Получаем маршрут через OSRM API
    route_response = requests.get(f"{OSRM_ROUTE_URL}{route_coords}?overview=full&geometries=geojson").json()

    if "routes" not in route_response or not route_response["routes"]:
        return None

    # Извлекаем геометрию маршрута и расстояние
    route_geometry = route_response["routes"][0]["geometry"]["coordinates"]
    route_points = [(point[1], point[0]) for point in route_geometry]
    initial_distance = route_response["routes"][0]["distance"]
    return route_points, initial_distance

def find_pharmacies_along_route(route_points):
    """
    Поиск аптек вдоль маршрута с использованием Overpass API.
    """
    pharmacies = []
    for i, point in enumerate(route_points):
        if i % 2 != 0:  # Берем каждую 2-ю точку маршрута
            continue
        print(i)
        # Формируем запрос для Overpass API
        overpass_query = f"""
        [out:json];
        node["amenity"="pharmacy"](around:500, {point[0]}, {point[1]});
        out;
        """
        try:
            # Отправляем запрос к Overpass API
            response = requests.get(OVERPASS_URL, params={"data": overpass_query})
            response.raise_for_status()
            data = response.json()
            pharmacies.extend([(node["lat"], node["lon"]) for node in data.get("elements", [])])
        except requests.exceptions.RequestException:
            continue
    
    if not pharmacies:
        return []
    # Удаляем дубликаты аптек и возвращаем результат
    return list(set(pharmacies))

def get_distance_matrix(locations):
    """
    Получение матрицы расстояний между точками с использованием OSRM Table API.
    """
    # Формируем строку координат для запроса к OSRM
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in locations])
    # Получаем матрицу расстояний через OSRM
    osrm_response = requests.get(f"{OSRM_TABLE_URL}{coords_str}?sources=all&destinations=all&annotations=distance").json()

    if "distances" not in osrm_response:
        return None

    return osrm_response["distances"]

def generate_route(locations, path):
    """
    Генерация финального маршрута через OSRM Route API.
    """
    route_coords = ";".join([f"{locations[i][1]},{locations[i][0]}" for i in path])
    # Получаем маршрут через OSRM Route API
    route_response = requests.get(f"{OSRM_ROUTE_URL}{route_coords}?overview=full&geometries=geojson").json()

    return {
        "geometry": route_response["routes"][0]["geometry"],        # Геометрия маршрута
        "distance": route_response["routes"][0]["distance"] / 1000, # Перевод в км
        "points": [locations[i] for i in path]                      # Список точек маршрута
    }


@app.get("/", response_class=HTMLResponse)
async def serve_map(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/find-route/")
async def find_route(home: str = Form(...), hospital: str = Form(...)):
    # Геодекодирование в координаты
    home_coords = get_coordinates(home)
    hospital_coords = get_coordinates(hospital)
    if not home_coords or not hospital_coords:
        return {"error": "Не удалось найти координаты адресов"}

    # Построение оптимального маршрута от больницы до дома
    route_points, init_dist = build_initial_route(hospital_coords, home_coords)
    pharmacies = find_pharmacies_along_route(route_points)
    if not pharmacies:
        return {"error": "Не найдено аптек вдоль маршрута"}

    # Собираем все точки: больница, аптеки, дом
    locations = [hospital_coords] + pharmacies + [home_coords]
    distances = get_distance_matrix(locations)

    # Выбираем три самые оптимальные аптеки
    hospital_index = 0
    home_index = len(locations) - 1
    pharmacy_indices = range(1, len(pharmacies) + 1)

    # Рассчитываем "стоимость" каждой аптеки
    pharmacy_scores = []
    for i in pharmacy_indices:
        # Стоимость = расстояние от больницы до аптеки + расстояние от аптеки до дома
        cost = distances[hospital_index][i] + distances[i][home_index]
        pharmacy_scores.append((cost, i))

    # Сортируем аптеки по стоимости и выбираем три лучших
    pharmacy_scores.sort()
    best_pharmacies = [index for _, index in pharmacy_scores[:3]]

    # Генерация маршрутов через выбранные аптеки
    all_paths = []
    for subset in itertools.permutations(best_pharmacies):  # Перебираем все варианты
        full_path = [0] + list(subset) + [-1]
        distance = sum(distances[full_path[i]][full_path[i + 1]] for i in range(len(full_path) - 1))
        all_paths.append((distance, full_path))

    # Сортируем по расстоянию и выбираем самый оптимальный маршрут
    all_paths.sort()
    best_path = all_paths[0]  # Берём самый короткий маршрут

    # Запрашиваем маршрут OSRM для самого оптимального маршрута
    optimal_route = generate_route(locations, best_path[1])

    # Возвращаем самый оптимальный маршрут
    return {"route": optimal_route}


@app.post("/most-vigoda/")
async def most_vigoda(home: str = Form(...), hospital: str = Form(...)):
    # Геодекодирование в координаты
    home_coords = get_coordinates(home)
    hospital_coords = get_coordinates(hospital)
    if not home_coords or not hospital_coords:
        return {"error": "Не удалось найти координаты адресов"}

    # Построение оптимального маршрута от больницы до дома
    route_points, initial_distance = build_initial_route(hospital_coords, home_coords)
    pharmacies = find_pharmacies_along_route(route_points)
    if not pharmacies:
        return {"error": "Не найдено аптек вдоль маршрута"}
    
    # Собираем все точки: больница, аптеки, дом
    locations = [hospital_coords] + pharmacies + [home_coords]
    distances = get_distance_matrix(locations)

    # Присваиваем случайные категории аптекам
    pharmacy_categories = {i: round(random.uniform(1.0, 2.0), 1) for i, _ in enumerate(pharmacies)}

    # Вычисление ценовой категории для каждой аптеки с учетом дополнительного расстояния до дома
    hospital_index = 0
    home_index = len(locations) - 1
    pharmacy_indices = range(1, len(pharmacies) + 1)
    best_pharmacy = None
    best_score = float('inf')

    # Вывод информации о всех аптеках
    for i in pharmacy_indices: 
        total_distance = distances[hospital_index][i] + distances[i][home_index]
        category = pharmacy_categories[i - 1] 
        distance_difference = total_distance - initial_distance 
        distance_difference = max(0, distance_difference) 
        effective_category = category + (distance_difference / 100) * 0.1

        # print(f"Аптека {i}:")
        # print(f"  Координаты: {pharmacies[i - 1]}")
        # print(f"  Ценовая категория: {category}")
        # print(f"  Расстояние от больницы до дома через аптеку: {total_distance:.2f} метров")
        # print(f"  Разница с изначальным расстоянием: {distance_difference:.2f} метров")
        # print(f"  Ценовая категория с учетом расстояния: {effective_category:.2f}\n")

        # Выбираем аптеку с минимальным коэфом
        if effective_category < best_score:
            best_score = effective_category
            best_pharmacy = i

    if best_pharmacy is None:
        return {"error": "Не удалось найти оптимальную аптеку"}

    # Генерация маршрута через выбранную аптеку
    route_coords = ";".join([
        f"{locations[hospital_index][1]},{locations[hospital_index][0]}",
        f"{locations[best_pharmacy][1]},{locations[best_pharmacy][0]}",
        f"{locations[home_index][1]},{locations[home_index][0]}"
    ])
    route_response = requests.get(f"{OSRM_ROUTE_URL}{route_coords}?overview=full&geometries=geojson").json()

    optimal_route = {
        "geometry": route_response["routes"][0]["geometry"],
        "distance": route_response["routes"][0]["distance"] / 1000,  # Перевод в км
        "points": [
            locations[hospital_index],
            locations[best_pharmacy],
            locations[home_index]
        ],
        "pharmacy_category": pharmacy_categories[best_pharmacy - 1],
        "effective_category": best_score
    }

    return {"route": optimal_route}