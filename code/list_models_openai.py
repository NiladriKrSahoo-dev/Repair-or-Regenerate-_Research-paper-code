import os, sys
from openai import OpenAI
base = sys.argv[1] if len(sys.argv) > 1 else "https://integrate.api.nvidia.com/v1"
env = sys.argv[2] if len(sys.argv) > 2 else "NVIDIA_API_KEY"
for m in sorted(x.id for x in OpenAI(base_url=base, api_key=os.environ[env]).models.list()): print(m)
