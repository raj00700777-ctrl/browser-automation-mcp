"""
Raj Browser MCP — Semantic Form Intelligence

Government/scholarship-portal forms are notorious for field names
like "txtBox2" or "field_47" -- the actual attribute tells you
nothing about what the field wants. Every other automation tool
either requires an exact CSS selector (useless when you don't
know what maps to what) or blind trial-and-error.

This module figures out what each field ACTUALLY wants by
combining every signal a real form gives a human: its <label>,
aria-label/aria-labelledby, placeholder, and -- critically, for
the badly-marked-up forms this is built for -- the nearest
preceding text in the DOM (a <td>, a <div>, a plain text node)
even when there's no proper <label> element at all.

Once a field's purpose is identified with reasonable confidence,
fill_form_from_profile() can fill it automatically from a
structured profile dict (keyed by purpose, e.g. "aadhar_number",
"father_name") -- and anything it's NOT confident about is
explicitly left alone for a human to handle, rather than guessing
and silently filling the wrong thing into a sensitive field.
"""

import re

from browser import browser


# ============================================================
# PAGE ACCESS
# ============================================================

async def _get_page():
    page = await browser.get_page()
    if page is None:
        raise RuntimeError("No active browser page available.")
    return page


# ============================================================
# PURPOSE TAXONOMY
# ============================================================
#
# Each purpose maps to keyword patterns checked against the
# field's combined label text. Order matters where patterns
# could overlap -- more specific patterns are listed first so
# e.g. "confirm password" is checked before the plain "password"
# pattern would otherwise claim it.

_PURPOSE_PATTERNS = [
    ("confirm_password", [r"confirm\s*password", r"re-?enter\s*password", r"retype\s*password"]),
    ("otp", [r"\botp\b", r"verification\s*code", r"one\s*time\s*password"]),
    ("captcha_input", [r"captcha"]),
    ("username", [r"user\s*name", r"user\s*id", r"login\s*id"]),
    ("password", [r"\bpassword\b", r"\bpwd\b"]),
    ("email", [r"e-?mail"]),
    ("phone", [r"mobile", r"phone", r"contact\s*number", r"whatsapp\s*number"]),
    ("father_name", [r"father'?s?\s*name", r"\bpita\b"]),
    ("mother_name", [r"mother'?s?\s*name", r"\bmata\b"]),
    ("full_name", [r"full\s*name", r"candidate\s*name", r"applicant\s*name", r"student\s*name", r"your\s*name", r"\bnaam\b"]),
    ("first_name", [r"first\s*name", r"given\s*name"]),
    ("last_name", [r"last\s*name", r"sur\s*name", r"family\s*name"]),
    ("date_of_birth", [r"date\s*of\s*birth", r"\bdob\b", r"birth\s*date"]),
    ("gender", [r"\bgender\b", r"\bsex\b"]),
    ("aadhar_number", [r"aadha?a?r"]),
    ("pan_number", [r"\bpan\s*(number|card|no)\b"]),
    ("category", [r"\bcategory\b", r"\bcaste\b"]),
    ("income", [r"annual\s*income", r"family\s*income", r"\bincome\b"]),
    ("bank_account", [r"account\s*number", r"bank\s*account"]),
    ("ifsc_code", [r"\bifsc\b"]),
    ("pincode", [r"pin\s*code", r"postal\s*code", r"\bzip\b"]),
    ("state", [r"\bstate\b", r"\bprovince\b"]),
    ("city", [r"\bcity\b", r"\btown\b"]),
    ("address_line", [r"\baddress\b", r"street", r"house\s*no"]),
    ("qualification", [r"qualification", r"\beducation\b", r"\bcourse\b"]),
    ("institution_name", [r"school\s*name", r"college\s*name", r"institution"]),
    ("roll_number", [r"roll\s*(number|no)", r"registration\s*number", r"enrollment"]),
    ("percentage", [r"percentage", r"\bmarks\b", r"\bcgpa\b", r"\bgpa\b"]),
]

_COMPILED_PATTERNS = [
    (purpose, [re.compile(p, re.IGNORECASE) for p in patterns])
    for purpose, patterns in _PURPOSE_PATTERNS
]


def classify_field(label_text: str):
    """Match combined label text against the purpose taxonomy. Returns (purpose, confidence 0-1)."""
    if not label_text:
        return "unknown", 0.0

    text = label_text.lower()
    for purpose, patterns in _COMPILED_PATTERNS:
        for pattern in patterns:
            if pattern.search(text):
                return purpose, 0.9
    return "unknown", 0.0


async def get_supported_purposes():
    return {"success": True, "purposes": [p for p, _ in _PURPOSE_PATTERNS]}


# ============================================================
# FIELD EXTRACTION (labels from every real-world signal)
# ============================================================

_EXTRACT_FIELDS_JS = r"""
(scopeSelector) => {
    const scope = scopeSelector ? document.querySelector(scopeSelector) : document.body;
    if (!scope) return [];

    const fields = Array.from(scope.querySelectorAll('input, select, textarea')).filter(el => {
        const type = (el.type || '').toLowerCase();
        return !['hidden', 'submit', 'button', 'reset', 'image'].includes(type);
    });

    function nearestPrecedingText(el) {
        // Walk up through parents; at each level, check the
        // immediately preceding sibling's text -- this is how
        // badly-marked-up table/div forms visually label fields
        // without ever using a real <label>.
        let node = el;
        for (let depth = 0; depth < 4 && node; depth++) {
            let sib = node.previousElementSibling;
            while (sib) {
                const text = (sib.innerText || sib.textContent || '').trim();
                if (text && text.length < 100) return text;
                sib = sib.previousElementSibling;
            }
            node = node.parentElement;
        }
        return '';
    }

    let counter = 0;
    return fields.map(el => {
        counter++;
        const ref = 'f' + counter;
        el.setAttribute('data-raj-form-ref', ref);

        let labelText = '';

        if (el.id) {
            const lbl = document.querySelector(`label[for="${el.id}"]`);
            if (lbl) labelText = (lbl.innerText || '').trim();
        }
        if (!labelText) {
            const parentLabel = el.closest('label');
            if (parentLabel) labelText = (parentLabel.innerText || '').trim();
        }
        if (!labelText && el.getAttribute('aria-label')) {
            labelText = el.getAttribute('aria-label').trim();
        }
        if (!labelText && el.getAttribute('aria-labelledby')) {
            const ids = el.getAttribute('aria-labelledby').split(/\s+/);
            labelText = ids.map(id => document.getElementById(id)?.innerText || '').join(' ').trim();
        }
        if (!labelText && el.placeholder) {
            labelText = el.placeholder.trim();
        }
        if (!labelText) {
            labelText = nearestPrecedingText(el);
        }

        const combinedSignal = [
            labelText, el.placeholder || '', el.name || '', el.id || '', el.getAttribute('aria-label') || '',
        ].join(' ').trim();

        return {
            ref,
            tag: el.tagName.toLowerCase(),
            type: el.type || (el.tagName.toLowerCase() === 'select' ? 'select' : 'text'),
            label_text: labelText,
            combined_signal: combinedSignal,
            current_value: el.value || '',
            required: !!el.required,
        };
    });
}
"""


async def analyze_form(selector: str = None):
    """
    Scan a form (or the whole page if selector is omitted) and
    classify what each field is actually asking for, using
    label/aria/placeholder/nearest-text-fallback -- returns each
    field's purpose and confidence, without filling anything.
    """
    try:
        page = await _get_page()
        raw_fields = await page.evaluate(_EXTRACT_FIELDS_JS, selector)

        analyzed = []
        for f in raw_fields:
            purpose, confidence = classify_field(f["combined_signal"])
            analyzed.append({
                "ref": f["ref"],
                "tag": f["tag"],
                "type": f["type"],
                "label_text": f["label_text"] or None,
                "detected_purpose": purpose,
                "confidence": confidence,
                "current_value": f["current_value"],
                "required": f["required"],
            })

        return {
            "success": True,
            "action": "analyze_form",
            "field_count": len(analyzed),
            "fields": analyzed,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# FILL FROM PROFILE
# ============================================================

# Purposes that must NEVER be auto-filled from a saved profile,
# even if matched with high confidence -- these are single-use/
# time-sensitive or security-sensitive by nature.
_NEVER_AUTOFILL = {"otp", "captcha_input", "confirm_password"}

# Purposes where typo-simulation should always be off, even if
# the caller asked for human-like typing -- numeric/ID fields
# where a stray character matters.
_NO_TYPO_PURPOSES = {
    "aadhar_number", "pan_number", "phone", "email", "pincode",
    "bank_account", "ifsc_code", "date_of_birth", "otp", "roll_number",
}


async def fill_form_from_profile(
    profile: dict,
    selector: str = None,
    use_human_typing: bool = True,
    dry_run: bool = False,
):
    """
    Analyze a form and fill every field it can confidently match
    against `profile` (a dict keyed by purpose, e.g.
    {"full_name": "...", "aadhar_number": "...", "email": "..."}).

    Fields it can't confidently classify, or that map to a
    NEVER_AUTOFILL purpose (OTP, CAPTCHA, confirm-password), are
    explicitly left alone and reported separately -- never guessed.

    dry_run=True analyzes and reports what WOULD be filled without
    actually typing anything -- useful to review before trusting it
    on a real government form.
    """
    try:
        analysis = await analyze_form(selector)
        if not analysis.get("success"):
            return analysis

        filled = []
        skipped = []

        for field in analysis["fields"]:
            purpose = field["detected_purpose"]
            ref = field["ref"]
            field_selector = f'[data-raj-form-ref="{ref}"]'

            if purpose == "unknown" or field["confidence"] < 0.5:
                skipped.append({**field, "reason": "purpose not confidently identified"})
                continue

            if purpose in _NEVER_AUTOFILL:
                skipped.append({**field, "reason": f"'{purpose}' fields are never auto-filled"})
                continue

            if purpose not in profile:
                skipped.append({**field, "reason": f"no '{purpose}' value in the supplied profile"})
                continue

            value = str(profile[purpose])

            if dry_run:
                filled.append({**field, "would_fill_value": value, "dry_run": True})
                continue

            try:
                if field["tag"] == "select":
                    page = await _get_page()
                    await page.locator(field_selector).select_option(label=value)
                elif use_human_typing:
                    import human
                    typo_rate = 0.0 if purpose in _NO_TYPO_PURPOSES else 0.02
                    await human.human_type(selector=field_selector, text=value, typo_rate=typo_rate, profile="fast")
                else:
                    import interaction
                    await interaction.type_text(field_selector, value, clear=True)

                filled.append({**field, "filled_value": value})

            except Exception as fill_error:
                skipped.append({**field, "reason": f"fill attempt failed: {fill_error}"})

        return {
            "success": True,
            "action": "fill_form_from_profile",
            "dry_run": dry_run,
            "filled_count": len(filled),
            "skipped_count": len(skipped),
            "filled": filled,
            "skipped": skipped,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "analyze_form",
    "fill_form_from_profile",
    "classify_field",
    "get_supported_purposes",
]
