import re
from rapidfuzz import fuzz

def ein_ok(v): return bool(re.fullmatch(r"\d{2}-\d{7}", (v or "").strip()))
def iban_ok(v):
    s=re.sub(r"\s+", "", (v or "").upper())
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}",s): return False
    x=s[4:]+s[:4]; n=''.join(str(ord(c)-55) if c.isalpha() else c for c in x)
    rem=0
    for c in n: rem=(rem*10+int(c))%97
    return rem==1
def gstin_ok(v):
    s=(v or "").upper().strip()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]",s): return False
    chars="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"; total=0; factor=2
    for c in reversed(s[:-1]):
        product=chars.index(c)*factor; total+=product//36+product%36; factor=1 if factor==2 else 2
    check=chars[(36-total%36)%36]
    return check==s[-1]
def pan_ok(v): return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]",(v or "").upper().strip()))
def ifsc_ok(v): return bool(re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}",(v or "").upper().strip()))
def aba_ok(v):
    s=(v or '').strip()
    return bool(re.fullmatch(r"\d{9}",s)) and sum(int(s[i])*w for i,w in enumerate([3,7,1]*3))%10==0
def normalize_name(name):
    s=re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    s=re.sub(r"\b(private|pvt|limited|ltd|llc|incorporated|inc|gmbh|corp|corporation|co)\b", " ", s)
    return " ".join(s.split())
def name_score(a,b):
    x,y=normalize_name(a),normalize_name(b)
    return max(fuzz.token_set_ratio(x,y),fuzz.ratio(x,y))/100 if x and y else 0
def individual_company_holder(vendor_type,legal_name,holder_name):
    return vendor_type=='company' and bool(holder_name) and name_score(legal_name,holder_name)<.75
