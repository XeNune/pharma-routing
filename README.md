# Routing Pharma Service

Этот проект предоставляет сервис на FastAPI для поиска оптимального маршрута от больницы до дома с возможностью посещения аптек по пути. Используется OpenStreetMap (OSM) и OSRM для построения маршрутов и Overpass API для поиска аптек.

## Функциональность
- Определение координат больницы и дома по адресу или широте и долготе.
- Построение маршрута от больницы до дома
- Поиск аптек вдоль маршрута
- Выбор оптимального маршрута с посещением аптек
- Оптимизация маршрута по ценовой категории аптек и дополнительного расстояния

## Технологии
- **Backend**: FastAPI, requests, itertools, random, time
- **Frontend**: HTML, JavaScript, Leaflet
- **APIs**: OpenStreetMap (Nominatim), Overpass API, OSRM


## Установка и запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/XeNune/pharma-routing.git
cd pharma-route
```

### 2. Сборка и запуск контейнера
```bash
docker build -t pharm-route-app .
docker run -d -p 8000:8000 --name pharm-route-app pharm-route-app
```
После запуска сервиса он будет доступен по адресу:
```
http://127.0.0.1:8000/
```

## Использование

1. Открыть `http://127.0.0.1:8000/` в браузере.
2. Ввести адреса больницы и дома.
3. Нажать «Построить маршрут» для получения оптимального маршрута через 3 аптеки.
4. Нажать «Выгодный маршрут», чтобы выбрать аптеку с лучшей ценовой категорией.

#### (время обработки может занять несколько минут потому что используются беслптные API с задержками)


## Пример работы
![image](https://github.com/user-attachments/assets/7c78b71e-40c6-4021-8ff4-068e732fdc30)

## API Эндпоинты

### `POST /find-route/`
#### Описание:
Возвращает оптимальный маршрут с тремя лучшими аптеками.
#### Параметры:
- `home` (строка) – адрес дома
- `hospital` (строка) – адрес больницы
#### Ответ:
```json
{
    "route": {
        "geometry": {"type": "LineString", "coordinates": [...]},
        "distance": 10.5,
        "points": [[55.75, 37.61], [55.76, 37.62], [55.77, 37.63]]
    }
}
```

### `POST /most-vigoda/`
#### Описание:
Возвращает маршрут с аптекой с лучшим соотношением цены и расстояния.
#### Параметры:
- `home` (строка) – адрес дома
- `hospital` (строка) – адрес больницы
#### Ответ:
```json
{
    "route": {
        "geometry": {"type": "LineString", "coordinates": [...]},
        "distance": 11.2,
        "points": [[55.75, 37.61], [55.76, 37.62], [55.77, 37.63]],
        "pharmacy_category": 1.5,
        "effective_category": 1.6
    }
}
```
