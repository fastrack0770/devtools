"""`ai-usage`: print the current usage document and exit.

stdout carries exactly one JSON document and nothing else — diagnostics go to
stderr — because two clients parse this stream and neither should have to skip
past a warning to find it.
"""

import json
import sys

from . import cache


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    try:
        document = cache.usage(force=force)
    except Exception as exc:   # never answer with a traceback on stdout
        print("ai-usage: %s" % exc, file=sys.stderr)
        from . import schema
        import time
        document = schema.document({}, int(time.time()))
    json.dump(document, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
