import sys, os
os.chdir('/Users/air/Desktop/ziwei-api')
import site
site.ENABLE_USER_SITE = True
sys.path.insert(0, site.getusersitepackages())
sys.path.insert(0, os.getcwd())
import uvicorn
uvicorn.run('api.main:app', host='0.0.0.0', port=8119)
