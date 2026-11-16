"""Run: python size_webapp.py  ->  http://127.0.0.1:8000 (stdlib only, Render ready)."""
import argparse
import importlib.util
import json
import os
import secrets
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
BACKEND_PATH = ROOT / 'size_recommender_gemini.py'
spec = importlib.util.spec_from_file_location('size_backend', BACKEND_PATH)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

CSRF_TOKEN = secrets.token_urlsafe(32)
CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_TTL = 15 * 60
FIELDS = ['length_cm', 'shoulder_cm', 'chest_width_cm', 'sleeve_cm']
PROFILE_PATH = ROOT / 'data' / 'fit_profile.json'
PROFILE_LOCK = threading.Lock()

# 대표 브랜드 & 무신사 스탠다드 최다 판매 상의 7종 S/M/L 실측표 기준 데이터
BRAND_PRESETS = {
    "musinsa_relax_tee": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 릴렉스 핏 크루넥 반팔 티셔츠",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100%",
            "stretch": "약간 있음",
        },
        "sizes": {
            "S": {"length_cm": 68.0, "shoulder_cm": 47.5, "chest_width_cm": 52.5, "sleeve_cm": 22.5},
            "M": {"length_cm": 70.0, "shoulder_cm": 49.5, "chest_width_cm": 55.0, "sleeve_cm": 23.5},
            "L": {"length_cm": 72.0, "shoulder_cm": 51.0, "chest_width_cm": 57.0, "sleeve_cm": 24.5},
        },
    },
    "musinsa_basic_tee": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 베이식 크루넥 반팔 티셔츠",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100%",
            "stretch": "보통",
        },
        "sizes": {
            "S": {"length_cm": 65.5, "shoulder_cm": 43.0, "chest_width_cm": 49.0, "sleeve_cm": 20.5},
            "M": {"length_cm": 67.5, "shoulder_cm": 45.0, "chest_width_cm": 51.5, "sleeve_cm": 21.5},
            "L": {"length_cm": 69.5, "shoulder_cm": 47.0, "chest_width_cm": 54.0, "sleeve_cm": 22.5},
        },
    },
    "musinsa_heavy_over_tee": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 헤비웨이트 오버사이즈 반팔 티셔츠",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100% (헤비웨이트)",
            "stretch": "적음",
        },
        "sizes": {
            "S": {"length_cm": 70.0, "shoulder_cm": 52.0, "chest_width_cm": 57.0, "sleeve_cm": 24.0},
            "M": {"length_cm": 72.0, "shoulder_cm": 54.0, "chest_width_cm": 59.5, "sleeve_cm": 25.0},
            "L": {"length_cm": 74.0, "shoulder_cm": 56.0, "chest_width_cm": 62.0, "sleeve_cm": 26.0},
        },
    },
    "musinsa_oxford_shirt": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 릴렉스 핏 옥스포드 셔츠",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100% (옥스포드)",
            "stretch": "없음",
        },
        "sizes": {
            "S": {"length_cm": 72.0, "shoulder_cm": 46.5, "chest_width_cm": 54.0, "sleeve_cm": 60.0},
            "M": {"length_cm": 74.0, "shoulder_cm": 48.0, "chest_width_cm": 56.5, "sleeve_cm": 61.5},
            "L": {"length_cm": 76.0, "shoulder_cm": 49.5, "chest_width_cm": 59.0, "sleeve_cm": 63.0},
        },
    },
    "musinsa_sweatshirt": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 릴렉스 핏 스웨트셔츠 (맨투맨)",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100% (시보리 밑단)",
            "stretch": "약간 있음",
        },
        "sizes": {
            "S": {"length_cm": 66.5, "shoulder_cm": 51.0, "chest_width_cm": 56.5, "sleeve_cm": 59.5},
            "M": {"length_cm": 68.5, "shoulder_cm": 53.0, "chest_width_cm": 59.0, "sleeve_cm": 61.0},
            "L": {"length_cm": 70.5, "shoulder_cm": 55.0, "chest_width_cm": 61.5, "sleeve_cm": 62.5},
        },
    },
    "musinsa_hoodie": {
        "product": {
            "product_name": "[실측기준] 무신사 스탠다드 릴렉스 핏 후드 스웨트셔츠",
            "brand": "MUSINSA STANDARD",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100% (시보리 밑단)",
            "stretch": "약간 있음",
        },
        "sizes": {
            "S": {"length_cm": 66.0, "shoulder_cm": 52.0, "chest_width_cm": 57.5, "sleeve_cm": 59.0},
            "M": {"length_cm": 68.0, "shoulder_cm": 54.0, "chest_width_cm": 60.0, "sleeve_cm": 60.5},
            "L": {"length_cm": 70.0, "shoulder_cm": 56.0, "chest_width_cm": 62.5, "sleeve_cm": 62.0},
        },
    },
    "uniqlo_u": {
        "product": {
            "product_name": "[실측기준] 유니클로 U 크루넥 반팔 티셔츠",
            "brand": "UNIQLO",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 100% (헤비웨이트)",
            "stretch": "보통",
        },
        "sizes": {
            "S": {"length_cm": 65.0, "shoulder_cm": 43.5, "chest_width_cm": 49.5, "sleeve_cm": 21.0},
            "M": {"length_cm": 68.0, "shoulder_cm": 45.5, "chest_width_cm": 52.5, "sleeve_cm": 22.0},
            "L": {"length_cm": 71.0, "shoulder_cm": 47.5, "chest_width_cm": 55.5, "sleeve_cm": 23.0},
        },
    },
    "nike_club": {
        "product": {
            "product_name": "[실측기준] 나이키 클럽 플리스 크루넥 맨투맨",
            "brand": "NIKE",
            "source_url": "https://www.musinsa.com/products/1032469",
            "material": "면 80%, 폴리에스터 20% (시보리 밑단)",
            "stretch": "약간 있음",
        },
        "sizes": {
            "S": {"length_cm": 66.0, "shoulder_cm": 47.0, "chest_width_cm": 54.0, "sleeve_cm": 61.0},
            "M": {"length_cm": 68.0, "shoulder_cm": 49.0, "chest_width_cm": 57.0, "sleeve_cm": 62.5},
            "L": {"length_cm": 70.0, "shoulder_cm": 51.5, "chest_width_cm": 60.0, "sleeve_cm": 64.0},
        },
    },
}


def load_profile():
    with PROFILE_LOCK:
        if not PROFILE_PATH.exists():
            return None
        try:
            profile = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
            if profile['version'] != 1 or not (1 <= len(profile['clothes']) <= 3):
                raise ValueError()
            return profile
        except (ValueError, KeyError, TypeError):
            raise RuntimeError('저장한 옷 정보를 읽지 못했습니다. 첫 화면에서 다시 등록해 주세요.') from None


def save_profile(data):
    preset_brand = data.get('preset_brand')
    preset_size = data.get('preset_size')

    if preset_brand:
        if preset_brand not in BRAND_PRESETS:
            raise ValueError('선택한 대표 상품을 찾을 수 없습니다.')
        brand_item = BRAND_PRESETS[preset_brand]
        if preset_size not in brand_item['sizes']:
            raise ValueError('S, M, L 중 사이즈를 선택해 주세요.')
        clothes = [{
            'product': brand_item['product'],
            'size': preset_size,
            'measurements': brand_item['sizes'][preset_size],
        }]
    else:
        raw_entries = data.get('clothes')
        if not isinstance(raw_entries, list):
            raise ValueError('대표 브랜드 상품을 선택하거나 무신사 URL을 입력해 주세요.')
        entries = [x for x in raw_entries if isinstance(x, dict) and str(x.get('url', '')).strip()]
        if not (1 <= len(entries) <= 3):
            raise ValueError('대표 브랜드 상품을 선택하거나, 잘 맞았던 옷 URL을 최소 1개 입력해 주세요.')
        validated = [(required_text(x, 'url'), required_text(x, 'size', 80)) for x in entries]
        ids = [backend.musinsa_product_id(url) for url, _ in validated]
        if len(set(ids)) != len(ids):
            raise ValueError('서로 다른 옷을 입력해 주세요.')
        clothes = []
        for index, (url, size) in enumerate(validated, 1):
            try:
                product = backend.fetch_product_from_url(url)
                ref = backend.build_reference_clothes(product, size)
            except backend.ProductRateLimitError:
                raise
            except (ValueError, RuntimeError) as exc:
                raise ValueError(f'{index}번째 옷: {exc}') from None
            clothes.append({'product': product, 'size': ref['purchased_size'], 'measurements': ref['measurements']})

    traits = {}
    for field in FIELDS:
        values = [x['measurements'][field] for x in clothes if x['measurements'].get(field) is not None]
        if values:
            traits[field] = {'min': min(values), 'max': max(values), 'average': round(sum(values) / len(values), 1), 'count': len(values)}
    profile = {'version': 1, 'saved_at': datetime.now().astimezone().isoformat(timespec='seconds'),
               'clothes': clothes, 'measurement_preferences': traits,
               'note': '잘 맞았던 옷의 실측 범위입니다. 신체 치수나 체형을 뜻하지 않습니다.'}
    with PROFILE_LOCK:
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = PROFILE_PATH.with_suffix('.tmp')
        temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(PROFILE_PATH)
    return profile


def required_text(data, key, maximum=2048):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{key}: 입력값을 확인해 주세요.')
    return value.strip()


def public_product(product):
    return {k: product.get(k) for k in ['product_name', 'brand', 'source_url', 'measurement_note',
            'material', 'material_status', 'material_source_url', 'reviews', 'reviews_status',
            'review_source_url', 'review_sort', 'review_limit', 'collection_warnings']}


def compare_products(data):
    if 'profile_index' in data:
        profile = load_profile()
        index = data['profile_index']
        if not profile or type(index) is not int or not (0 <= index < len(profile['clothes'])):
            raise ValueError('첫 화면에서 잘 맞았던 옷을 먼저 등록해 주세요.')
        saved = profile['clothes'][index]
        reference_url = saved['product']['source_url']
        target_url = required_text(data, 'target_url')
        fit = required_text(data, 'desired_fit', 160)
        target_id = backend.musinsa_product_id(target_url)
        old = saved['product']
        reference = {
            'reference_url': reference_url,
            'product_name': old['product_name'],
            'purchased_size': saved['size'],
            'fit_satisfaction': '잘 맞음',
            'material': old.get('material'),
            'stretch': old.get('stretch'),
            'desired_fit': fit,
            'measurements': dict(saved['measurements']),
        }
        new = backend.fetch_product_from_url(target_url)
    else:
        reference_url = required_text(data, 'reference_url')
        target_url = required_text(data, 'target_url')
        size = required_text(data, 'reference_size', 80)
        fit = required_text(data, 'desired_fit', 160)
        reference_id = backend.musinsa_product_id(reference_url)
        target_id =
