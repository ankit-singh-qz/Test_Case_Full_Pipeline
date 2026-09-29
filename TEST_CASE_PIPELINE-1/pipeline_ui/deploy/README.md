# Host the QA site on a free Oracle VM

The website and the four pipelines run on an Oracle Cloud Always Free virtual machine. QA opens the page from any browser. This PC can be off. Bedrock model calls are still billed to the key in `.env`.

The application does not create the Oracle account or the virtual machine. Do those steps first.

## 1. Instance

Create an Always Free Ampere instance:

- Ubuntu 22.04
- About 2 OCPUs and 12 GB RAM
- A public IPv4 address

The smaller always-free micro shape has about 1 GB of RAM, which is too small for these pipelines.

Open inbound TCP 8000 in the subnet security list, and inbound TCP 22 from your own IP. In the VM firewall as well:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

## 2. Copy the code

From your machine, copy this whole project folder to the instance. Do not copy a local `.env` if it contains a short-lived token you do not want on the server. The Bedrock key belongs only in the server's `.env`.

```bash
scp -r Test_Case_Generation_Full_Pipeline ubuntu@<public-ip>:/tmp/pipelines
```

On the instance:

```bash
sudo mkdir -p /opt/pipelines
sudo mv /tmp/pipelines/* /opt/pipelines/
sudo chown -R ubuntu:ubuntu /opt/pipelines
```

`/opt/pipelines` must contain `run_full_pipeline.py`, `.env`, and the four pipeline folders.

## 3. Python

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv
python3.11 -m venv /opt/pipelines/.venv
source /opt/pipelines/.venv/bin/activate
pip install -r /opt/pipelines/FDD_PIPELINE-1/requirements.txt
pip install -r /opt/pipelines/TDD_PIPELINE-1/requirements.txt
pip install -r /opt/pipelines/TEST_DESIGN_PIPELINE-1/requirements.txt
pip install -r /opt/pipelines/TEST_CASE_PIPELINE-1/requirements.txt
pip install -r /opt/pipelines/TEST_CASE_PIPELINE-1/pipeline_ui/requirements.txt
```

The site starts `run_full_pipeline.py` with this same Python.

## 4. Environment file

Create `/opt/pipelines/.env` on the server. Copy the keys from `.env.example` and fill in the Bedrock key and a site password:

```bash
LLM_PROVIDER=bedrock
AWS_REGION=eu-north-1
AWS_BEARER_TOKEN_BEDROCK=<long-lived bedrock api key>
BEDROCK_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0
SITE_PASSWORD=<password you will send to QA>
```

Use an inference profile id for `eu-north-1`, not a foundation-model id from another region. QA never sees this file. They only type `SITE_PASSWORD` on the page.

## 5. App service

```bash
sudo cp /opt/pipelines/TEST_CASE_PIPELINE-1/pipeline_ui/deploy/pipeline-ui.service /etc/systemd/system/pipeline-ui.service
sudo systemctl daemon-reload
sudo systemctl enable --now pipeline-ui
sudo systemctl status pipeline-ui
```

The service listens on `0.0.0.0:8000` and starts again after a reboot.

## 6. What QA does

Open `http://<public-ip>:8000`, enter the site password, paste a refined user story, and press Generate.

When the run finishes, download:

- FDD PDF
- TDD PDF
- Test design PDF
- Test cases Excel

Only one Generate click runs at a time. A second click while a job is running is rejected. If a stage fails, the page shows the error and still offers whichever of those four files were already written.

HTTPS needs a domain name. Until you have one, the shareable address is the HTTP URL above.
