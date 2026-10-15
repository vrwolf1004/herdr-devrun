"""테스트 공통 준비. src 를 import 경로에 넣고, 문구 비교가 흔들리지 않게 언어를 en 으로 고정한다.

    python -m unittest discover -s tests
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import i18n  # noqa: E402

i18n.set_language("en")
