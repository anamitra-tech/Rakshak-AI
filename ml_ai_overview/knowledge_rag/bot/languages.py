"""
Shared 12-language menu/alias table — same BCP-47 tags as the Android app's
FamilySetupActivity.spokenLanguages and SarvamLanguageCodes. Originally
defined only inside webhook/app.py; extracted here so bot.agent.chat()'s
LANGUAGE_CHANGE intent (free-text language switches mid-conversation, e.g.
"reply to me in Tamil") can resolve a name to a tag using the exact same
table webhook/app.py's first-contact menu and _parse_language_selection
already use, instead of a second copy that could drift out of sync.
"""

# Hindi-first/English-second ordering matches the first-contact WhatsApp
# menu convention (CLAUDE.md 9.2 distinguishes this from Android's
# English-first Spinner, a different UI context).
LANGUAGE_MENU: list[tuple[str, str, str]] = [
    ("hi-IN", "हिन्दी", "Hindi"),
    ("en-IN", "English", "English"),
    ("bn-IN", "বাংলা", "Bengali"),
    ("mr-IN", "मराठी", "Marathi"),
    ("te-IN", "తెలుగు", "Telugu"),
    ("ta-IN", "தமிழ்", "Tamil"),
    ("gu-IN", "ગુજરાતી", "Gujarati"),
    ("ur-IN", "اردو", "Urdu"),
    ("kn-IN", "ಕನ್ನಡ", "Kannada"),
    ("ml-IN", "മലയാളം", "Malayalam"),
    ("pa-IN", "ਪੰਜਾਬੀ", "Punjabi"),
    ("or-IN", "ଓଡ଼ିଆ", "Odia"),
]

# Built from LANGUAGE_MENU so it can never drift out of sync with it: each
# language is resolvable by its menu number, its English name, or its native
# self-name (all lowercased for matching).
LANGUAGE_ALIASES: dict[str, str] = {}
for _i, (_tag, _native, _english) in enumerate(LANGUAGE_MENU, start=1):
    LANGUAGE_ALIASES[str(_i)] = _tag
    LANGUAGE_ALIASES[_english.lower()] = _tag
    LANGUAGE_ALIASES[_native.lower()] = _tag


def to_sarvam_lang_code(tag: str) -> str:
    """Mirrors the Android app's SarvamLanguageCodes.toSarvamCode: Sarvam
    uses "od-IN" for Odia, not the standard BCP-47 "or-IN" this project's
    preference store otherwise uses throughout."""
    return "od-IN" if tag.lower() == "or-in" else tag


def parse_language_selection(text: str) -> str | None:
    """None if `text` isn't a recognized language-selection reply (a menu
    number 1-12, an English language name, or a native self-name); else the
    selected BCP-47 tag. Exact-match only — free-text mentions like "switch
    to Tamil please" are NOT matched here (that's bot.agent's LANGUAGE_CHANGE
    intent, which extracts a language name from free text via the LLM
    classifier, then resolves it through english_name_to_tag() below)."""
    return LANGUAGE_ALIASES.get(text.strip().lower())


def english_name_to_tag(name: str) -> str | None:
    """Resolves a bare English or native language name (no menu numbers) to
    its BCP-47 tag — used by bot.agent's LANGUAGE_CHANGE handling once the
    LLM classifier has already extracted a language name from free text."""
    if not name:
        return None
    key = name.strip().lower()
    tag = LANGUAGE_ALIASES.get(key)
    if tag:
        return tag
    # LANGUAGE_ALIASES also contains "1".."12" keys; guard against a bare
    # digit being passed through as a "name" and matching one of those.
    if key.isdigit():
        return None
    return None


def english_name_for_tag(tag: str) -> str | None:
    return next((english for t, _native, english in LANGUAGE_MENU if t == tag), None)
