"""Keep direct python -m invocations consistent with run.sh."""
import os
import site
import sys

if site.ENABLE_USER_SITE:
    os.environ['PYTHONNOUSERSITE'] = '1'
    os.execv(sys.executable, [sys.executable, '-s', '-m', 'facial_expression_control', *sys.argv[1:]])

from .app import main
raise SystemExit(main())
