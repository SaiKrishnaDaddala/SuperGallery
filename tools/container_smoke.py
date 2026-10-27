"""Exercise a disposable container's HTTPS setup, auth and feature gates."""
import http.cookiejar
import json
import ssl
import time
import urllib.error
import urllib.request

context=ssl.create_default_context(cafile='/config/tls/server.crt')
opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path,body=None,method=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request('https://localhost:8843'+path,data=data,method=method,headers={'Content-Type':'application/json','X-SG-Request':'1'})
    try:
        with opener.open(req,timeout=15) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)


for attempt in range(40):
    try:
        if request('/api/auth')[0]==200:break
    except (urllib.error.URLError,TimeoutError,ConnectionError):
        pass
    time.sleep(1)
else:
    raise RuntimeError('HTTPS listener did not become ready')
assert request('/api/features')[0]==401
assert request('/api/setup',{'password':'synthetic-container-test-password'})[0]==200
status,features=request('/api/features')
assert status==200 and features['version']=='2.4.0'
assert request('/api/features',{'values':{'uploads':False,'people':False}},'PUT')[0]==200
assert request('/api/people')[0]==403
assert request('/api/upload',{},'POST')[0]==403
assert request('/api/network')[1]['enabled'] is False
assert request('/api/logout',{})[0]==200
assert request('/api/features')[0]==401
print('HTTPS certificate verification, first-run setup, auth, feature gates and remote-off defaults passed.')
