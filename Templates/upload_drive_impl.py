#!/usr/bin/env python3
import base64,json,os,subprocess,tempfile,time,urllib.request,urllib.parse,sys

def b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def post(url,data):
 r=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
 with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read())
def token(path):
 sa=json.load(open(path)); now=int(time.time()); h=b64(json.dumps({'alg':'RS256','typ':'JWT'},separators=(',',':')).encode()); c=b64(json.dumps({'iss':sa['client_email'],'scope':'https://www.googleapis.com/auth/drive.file','aud':sa['token_uri'],'iat':now,'exp':now+3600},separators=(',',':')).encode()); unsigned=(h+'.'+c).encode()
 fd,key=tempfile.mkstemp(prefix='ump-',suffix='.pem'); os.close(fd); os.chmod(key,0o600)
 try:
  open(key,'w').write(sa['private_key'].replace('\\n','\n'))
  sig=subprocess.check_output(['openssl','dgst','-sha256','-sign',key],input=unsigned)
 finally:
  try: os.remove(key)
  except: pass
 return post(sa['token_uri'],{'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer','assertion':unsigned.decode()+'.'+b64(sig)})['access_token']
def upload(tok,folder,path):
 size=os.path.getsize(path); meta=json.dumps({'name':os.path.basename(path),'parents':[folder]}).encode(); url='https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable'
 r=urllib.request.Request(url,data=meta,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':'application/octet-stream','X-Upload-Content-Length':str(size)},method='POST')
 with urllib.request.urlopen(r,timeout=60) as x: loc=x.headers['Location']
 with open(path,'rb') as f:data=f.read()
 r=urllib.request.Request(loc,data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/octet-stream','Content-Length':str(len(data))},method='PUT')
 with urllib.request.urlopen(r,timeout=3600) as x: print('[UMP] Drive:',x.read().decode())
if __name__=='__main__': upload(token(os.environ['UMP_DRIVE_SERVICE_ACCOUNT_JSON']),os.environ['UMP_DRIVE_FOLDER_ID'],sys.argv[1])
