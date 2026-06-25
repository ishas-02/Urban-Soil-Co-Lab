"""
One-time check: does our local quickXorHash match SharePoint's?
Pick a file that already exists in SharePoint AND locally, compare hashes.

    export SP_TENANT_ID=... SP_CLIENT_ID=... SP_CLIENT_SECRET=...
    python verify_hash.py site_configs/site_configs.json
"""
import os, sys, base64, requests, msal

REL = sys.argv[1] if len(sys.argv) > 1 else "site_configs/site_configs.json"
DATA_DIR = os.environ.get("SOIL_DATA_DIR", "./data")
TENANT_ID = os.environ["SP_TENANT_ID"]
CLIENT_ID = os.environ.get("SP_CLIENT_ID", "448531da-6d44-4729-8761-3f518ad44bfa")
CLIENT_SECRET = os.environ["SP_CLIENT_SECRET"]
SITE_ID = ("ubuffalo.sharepoint.com,5f018493-39ef-46af-a3cd-7ac32fed4007,"
           "7d18843c-7584-4fd4-885f-9ebd21322727")
SP_ROOT = "Urban Soil Co-Lab"
GRAPH = "https://graph.microsoft.com/v1.0"

class QuickXorHash:
    WIDTH=160; SHIFT=11
    def __init__(self):
        self._data=[0]*((self.WIDTH//64)+(1 if self.WIDTH%64 else 0)); self._length=0; self._shift=0
    def update(self,b):
        cur=self._shift; data=self._data
        for i in range(len(b)):
            idx=cur//64; bit=cur%64
            data[idx]^=(b[i]<<bit)&0xFFFFFFFFFFFFFFFF
            if bit>(64-8): data[(idx+1)%len(data)]^=b[i]>>(64-bit)
            cur+=self.SHIFT
            if cur>=self.WIDTH: cur-=self.WIDTH
        self._shift=(self._shift+self.SHIFT*(len(b)%self.WIDTH))%self.WIDTH; self._length+=len(b)
    def digest(self):
        out=bytearray((self.WIDTH+7)//8)
        for i in range(len(self._data)):
            for j in range(8):
                bidx=i*8+j
                if bidx<len(out): out[bidx]=(self._data[i]>>(8*j))&0xFF
        ln=self._length
        for i in range(8): out[(self.WIDTH//8)-8+i]^=(ln>>(8*i))&0xFF
        return bytes(out)
    def b64(self): return base64.b64encode(self.digest()).decode()

app=msal.ConfidentialClientApplication(CLIENT_ID,authority=f"https://login.microsoftonline.com/{TENANT_ID}",client_credential=CLIENT_SECRET)
tok=app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])["access_token"]
H={"Authorization":f"Bearer {tok}"}

r=requests.get(f"{GRAPH}/sites/{SITE_ID}/drive/root:/{SP_ROOT}/{REL}",headers=H)
if r.status_code!=200:
    print(f"Could not fetch '{REL}' from SharePoint: {r.status_code}"); sys.exit(1)
sp_hash=r.json().get("file",{}).get("hashes",{}).get("quickXorHash")

h=QuickXorHash()
with open(os.path.join(DATA_DIR,REL),"rb") as f: h.update(f.read())
local_hash=h.b64()

print(f"File: {REL}")
print(f"  SharePoint quickXorHash: {sp_hash}")
print(f"  Local computed:          {local_hash}")
print(f"  MATCH: {sp_hash==local_hash}")