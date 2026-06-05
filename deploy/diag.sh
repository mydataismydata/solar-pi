#!/usr/bin/env bash
echo "=== sudo passwordless? ==="
sudo -n true 2>&1; echo "sudo_rc=$?"
echo "=== venv module ==="
python3 -m venv --help >/dev/null 2>&1; echo "venv_rc=$?"
echo "=== ensurepip available? ==="
python3 -c "import ensurepip" 2>&1; echo "ensurepip_rc=$?"
echo "=== pip present? ==="
python3 -m pip --version 2>&1 | head -1
echo "=== internet to PyPI? ==="
curl -s -o /dev/null -w "http=%{http_code}\n" --max-time 8 https://pypi.org/simple/ 2>&1
echo "=== mem / disk ==="
free -h | awk 'NR==1 || /Mem/'
df -h / | awk 'NR==1 || NR==2'
