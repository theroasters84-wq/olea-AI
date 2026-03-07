import os
from efarmogi import efarmogi

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    efarmogi.run(host='0.0.0.0', port=port, debug=True)