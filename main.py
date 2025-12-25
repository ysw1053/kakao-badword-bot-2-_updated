from fastapi import FastAPI
from pydantic import BaseModel
import re

app = FastAPI()

BAD_WORDS = ["씨발", "시발", "ㅅㅂ", "병신", "지랄", "좆"]


_RE_KEEP = re.compile(r"[^0-9a-zA-Z가-힣ㄱ-ㅎㅏ-ㅣ]+")
_RE_REPEAT = re.compile(r"(.)\1{2,}")  

def basic_clean(s: str) -> str:
    s = s.lower()
    s = _RE_KEEP.sub("", s)           
    s = _RE_REPEAT.sub(r"\1\1", s)    
    return s


HANGUL_BASE = 0xAC00
HANGUL_END  = 0xD7A3

CHOSUNG_LIST = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNGSUNG_LIST = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONGSUNG_LIST = "\0ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

ENG2JAMO = {
    # 자음
    'r':'ㄱ','R':'ㄲ','s':'ㄴ','e':'ㄷ','E':'ㄸ','f':'ㄹ','a':'ㅁ','q':'ㅂ','Q':'ㅃ',
    't':'ㅅ','T':'ㅆ','d':'ㅇ','w':'ㅈ','W':'ㅉ','c':'ㅊ','z':'ㅋ','x':'ㅌ','v':'ㅍ','g':'ㅎ',
    # 모음
    'k':'ㅏ','o':'ㅐ','i':'ㅑ','O':'ㅒ','j':'ㅓ','p':'ㅔ','u':'ㅕ','P':'ㅖ','h':'ㅗ',
    'y':'ㅛ','n':'ㅜ','b':'ㅠ','m':'ㅡ','l':'ㅣ',
}
VOWEL_COMB = {
    ('ㅗ','ㅏ'):'ㅘ', ('ㅗ','ㅐ'):'ㅙ', ('ㅗ','ㅣ'):'ㅚ',
    ('ㅜ','ㅓ'):'ㅝ', ('ㅜ','ㅔ'):'ㅞ', ('ㅜ','ㅣ'):'ㅟ',
    ('ㅡ','ㅣ'):'ㅢ',
}
JONG_COMB = {
    ('ㄱ','ㅅ'):'ㄳ', ('ㄴ','ㅈ'):'ㄵ', ('ㄴ','ㅎ'):'ㄶ',
    ('ㄹ','ㄱ'):'ㄺ', ('ㄹ','ㅁ'):'ㄻ', ('ㄹ','ㅂ'):'ㄼ',
    ('ㄹ','ㅅ'):'ㄽ', ('ㄹ','ㅌ'):'ㄾ', ('ㄹ','ㅍ'):'ㄿ', ('ㄹ','ㅎ'):'ㅀ',
    ('ㅂ','ㅅ'):'ㅄ',
}

CHO_SET = set(CHOSUNG_LIST)
JUNG_SET = set(JUNGSUNG_LIST)
JONG_SET = set(JONGSUNG_LIST[1:])

def is_hangul_syllable(ch: str) -> bool:
    o = ord(ch)
    return HANGUL_BASE <= o <= HANGUL_END

def compose_hangul(cho, jung, jong=None):
    jong = jong or "\0"
    cho_i = CHOSUNG_LIST.index(cho)
    jung_i = JUNGSUNG_LIST.index(jung)
    jong_i = JONGSUNG_LIST.index(jong) if jong != "\0" else 0
    return chr(HANGUL_BASE + 588*cho_i + 28*jung_i + jong_i)

def eng_to_kor(s: str) -> str:
    jamos = []
    for ch in s:
        jamos.append(ENG2JAMO.get(ch, ch))

    out = []
    cho = jung = jong = None

    def flush():
        nonlocal cho, jung, jong
        if cho and jung:
            out.append(compose_hangul(cho, jung, jong))
        else:
            if cho: out.append(cho)
            if jung: out.append(jung)
            if jong: out.append(jong)
        cho = jung = jong = None

    i = 0
    while i < len(jamos):
        cur = jamos[i]

        if cur not in CHO_SET and cur not in JUNG_SET and cur not in JONG_SET:
            flush()
            out.append(cur)
            i += 1
            continue

        if cur in JUNG_SET:
            if cho is None:
                flush()
                out.append(cur)
            elif jung is None:
                jung = cur
            else:
                comb = VOWEL_COMB.get((jung, cur))
                if comb:
                    jung = comb
                else:
                    flush()
                    out.append(cur)
            i += 1
            continue

        if cho is None:
            cho = cur
        elif jung is None:
            flush()
            cho = cur
        else:
            if jong is None:
                jong = cur
            else:
                comb = JONG_COMB.get((jong, cur))
                if comb:
                    jong = comb
                else:
                    flush()
                    cho = cur
        i += 1

    flush()
    return "".join(out)


def decompose_hangul(text: str) -> str:
    out = []
    for ch in text:
        if not is_hangul_syllable(ch):
            out.append(ch)
            continue
        code = ord(ch) - HANGUL_BASE
        cho = code // 588
        jung = (code % 588) // 28
        jong = code % 28
        out.append(CHOSUNG_LIST[cho])
        out.append(JUNGSUNG_LIST[jung])
        if jong != 0:
            out.append(JONGSUNG_LIST[jong])
    return "".join(out)


CANON_MAP = {
    # 예시(원하면 지워도 됨):
    # "ㅆ": "ㅅ",
    # "ㄲ": "ㄱ",
    # "ㅐ": "ㅔ",
}

def canonize(text: str) -> str:
    return "".join(CANON_MAP.get(ch, ch) for ch in text)

def generate_forms(raw: str) -> set[str]:
    t0 = basic_clean(raw)
    t1 = leet_normalize(t0)

    t2 = basic_clean(eng_to_kor(t0))

    forms = set()
    for t in (t0, t1, t2):
        forms.add(t)
        j = decompose_hangul(t)
        forms.add(j)
        forms.add(canonize(j))
    return forms

def build_bad_forms(badwords: list[str]) -> set[str]:
    out = set()
    for w in badwords:
        for f in generate_forms(w):
            if f:
                out.add(f)
    return out

BAD_FORMS = build_bad_forms(BAD_WORDS)

def detect(message: str) -> bool:
    forms = generate_forms(message)
  
    for form in forms:
        for bw in BAD_FORMS:
            if bw in form:
                return True
    return False

class KakaoRequest(BaseModel):
    userRequest: dict

@app.post("/skill")
def detect_badword(req: KakaoRequest):
    utter = req.userRequest.get("utterance", "")
    detected = detect(utter)

    if detected:
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": f"⚠️ 욕설 감지됨\n\n{utter}"
                        }
                    }
                ]
            }
        }

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": ""}}
            ]
        }
    }
