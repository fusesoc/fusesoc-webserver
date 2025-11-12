[![CI](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/ci.yml)
[![Docs](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/docs.yml)
[![Docker](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/fusesoc/fusesoc-webserver/actions/workflows/docker.yml)
[![Developer Docs](https://img.shields.io/badge/docs-source--code--reference-blue)](https://fusesoc.github.io/fusesoc-webserver/)
# FuseSoC Package Database (FuseSoC-PD)

FuseSoC Package Database (FuseSoC-PD) is a web-based platform and RESTful API designed to manage, validate, and distribute [FuseSoC](https://fusesoc.github.io/) core packages. It provides both a user-friendly web interface and a robust API for interacting with a centralized collection of hardware IP cores, making it easier for developers and organizations to share, discover, and reuse hardware designs.

The system is built with Django and Django REST Framework, and uses a GitHub repository as the canonical source of truth for all core package data. Core files are stored, retrieved, and versioned directly on GitHub, ensuring transparency and traceability. The application supports core file validation against both JSON schemas and FuseSoC’s own parser, and allows users to publish new cores or validate existing ones through the API or web UI.

**Key features include:**
- 🖥️ **Web UI** for browsing, searching, and viewing details of available cores, vendors, and libraries.
- 🔗 **REST API** for programmatic access to core listing, download, validation, and publishing.
- 🔒 **GitHub Integration** for storing and retrieving core files, ensuring all data is version-controlled and easily auditable.
- 🔄 **Automated Database Initialization** from the GitHub repository.
- 📄 **OpenAPI Documentation** with interactive Swagger and ReDoc interfaces.
- 🚦 **Rate Limiting** and security best practices for safe public deployment.

FuseSoC-PD is ideal for teams and communities who want a reliable, transparent, and automated way to manage their FuseSoC core libraries, with the flexibility of both web and API access.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Database Consistency & Initialization](#database-consistency--initialization)
- [API Endpoints](#api-endpoints)
- [Web UI](#web-ui)
- [SPDX License List Management](#spdx-license-list-management)
- [Environment Variables](#environment-variables)
- [Development](#development)
  - [VS Code Configuration](#vs-code-configuration)
- [HTTP/HTTPS and DJANGO_DEBUG](#httphttps-and-django_debug)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)
- [License](#license)

---

## Quick Start

1. **Clone & Configure**
    ```bash
    git clone https://github.com/fusesoc/fusesoc-webserver.git
    cd fusesoc-webserver
    cp .env.example .env  # Copy example env and edit as needed
    ```

2. **Configure Environment**
    - Edit `.env` to set up your storage backend and other settings.
    - **For local development**, set:
      ```
      DJANGO_DEBUG=True
      ```
      This allows you to run the server using HTTP at [http://localhost:8000](http://localhost:8000).
    - By default, the server enforces HTTPS for production safety. Setting `DJANGO_DEBUG=True` disables HTTPS enforcement and enables easier local testing.

3. **Build & Run with Docker**
    ```bash
    docker compose up --build
    ```
    App runs at [http://localhost:8000](http://localhost:8000) (if `DJANGO_DEBUG=True`).

    > **Note on static files:**
    > Static files are automatically collected to the `/staticfiles` directory inside the Docker container during build or startup.
    > By default, static files are served by [WhiteNoise](https://whitenoise.evans.io/) within the Django application.
    > For larger or production deployments, you may optionally configure a dedicated web server (such as Nginx or Caddy) to serve static files from `/staticfiles`.

---

## Database Consistency & Initialization

**Note:**
The database is not the primary source of truth. All core package data is stored in the configured backend storage (by default, a GitHub repository, but you can use any Django-compatible storage backend).

**If the database is empty on application startup, it will automatically be initialized from the backend storage.**
This ensures the database always matches the storage contents. You can also manually re-initialize the database at any time using:

```bash
python manage.py init_db
```

This command reads all .core and .sig files from the configured storage backend (GitHub, S3, local filesystem, etc.) and populates the database accordingly.
The database can always be rebuilt from the backend storage, ensuring consistency with the canonical source.
Do not rely on the database as a persistent store for core data; the backend storage is the canonical source.

Storage Backend Configuration:

All storage backend and application configuration is managed via environment variables in your .env file.
Copy .env.example to .env and update the values as needed for your deployment.
To select the storage backend, set the STORAGE_BACKEND variable in .env:
# Options: 'local', 'github', 's3'
STORAGE_BACKEND=local
The actual storage class is determined in settings.py based on this alias. For example:
local → Local filesystem storage
github → GitHub-backed storage
s3 → S3 compatible storage
For S3, GitHub, or other backends, set any required credentials in .env as shown in .env.example.
If your storage backend supports cache prefill (e.g. for GitHub), the init_db command will use it automatically for efficient initialization.

Note: If you update the SPDX license list while the server is running, the changes will only take effect after you restart the application/server. This ensures the new license data is loaded into memory.

The command downloads the latest SPDX license list and stores it at the path specified by the SPDX_LICENSES_PATH setting in your Django configuration.

---

## API Endpoints

All endpoints are under `/api/v1/`:

| Endpoint                   | Method | Description                              |
|----------------------------|--------|------------------------------------------|
| `/health/`                 | GET    | API health check                         |
| `/list/?filter=...`        | GET    | List available core packages             |
| `/get/?core=...`           | GET    | Download a `.core` file by VLNV name     |
| `/get_archive/`            | GET    | Download a `.zip` file with all cores    |
| `/validate/`               | POST   | Validate a core file (`multipart/form`)  |
| `/publish/`                | POST   | Publish a core file to GitHub            |

- **Download (`/get/`)**: Provide the `core` query parameter with the full VLNV (e.g., `acme:lib1:foo:1.0.0`).
- **Validation and publishing**: Upload core files (and optional signatures) via `multipart/form-data`.
- **OpenAPI/Swagger docs**: Interactive documentation is available at `/api/v1/docs/swagger/` and `/api/v1/docs/redoc/`.

---

## Web UI
Easily search and browse packages in a clean interface.

<img src="docs/screenshots/web-ui.jpg" alt="Web UI screenshot" style="border: 2px solid #888; border-radius: 8px; max-width: 100%;">

- `/` — Landing page (core and vendor counts)
- `/cores/` — List all core packages (with optional search)
- `/core/<id>/` — Core detail by database ID
- `/cores/<vendor>/<library>/<core>/<version>/` — Core detail by VLNV (vendor, library, name, version)
- `/vendors/` — List all vendors (with optional search)
- `/vendors/<sanitized_name>/` — Vendor detail (with libraries and projects)
- `/fusesoc_pd` — Shortcut to API endpoint `get_archive`

---

## SPDX License List Management

FuseSoC-PD uses the [SPDX license list](https://spdx.org/licenses/) to validate and display license information for core packages.

- The license list is automatically updated when running the Docker container.
- You can manually update the license list at any time by running:

    ```bash
    python manage.py update_spdx_licenses
    ```

---

## Environment Variables

All required environment variables are listed in `.env.example`.
Copy this file to `.env` and update the values as needed.
## Development

To set up a development environment for FuseSoC-PD:

1. **Clone the repository:**
    ```bash
    git clone https://github.com/fusesoc/fusesoc-webserver.git
    cd fusesoc-webserver
    ```

2. **Set up a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install development dependencies:**
    ```bash
    pip install -r requirements-dev.txt
    ```

4. **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```

5. **Run the development server:**
    ```bash
    python manage.py runserver
    ```
    - By default, the server will run with HTTPS enforcement unless `DJANGO_DEBUG=True` is set in your `.env`.
    - For local development, ensure `DJANGO_DEBUG=True` in your `.env` to allow HTTP.

6. **(Optional) Build documentation locally:**
    ```bash
    sphinx-build -b html docs/source docs/build
    # Open docs/build/index.html in your browser
    ```

---

### VS Code Configuration

This repository includes recommended Visual Studio Code settings and launch configurations for a smooth development experience.

- **Debug Django server:**
  Launch the Django development server with the built-in debugger.

- **Debug tests:**
  Easily debug individual test files.

- **Pytest integration:**
  Pytest is enabled by default for test discovery and running tests.

> **Tip:** It is recommended to create and select a Python virtual environment (`venv`) in VS Code for isolated development.

**To use:**
1. Open the project folder in VS Code.
2. **Create a virtual environment:**
   Open the Command Palette (`Ctrl+Shift+P`), type `Python: Create Environment`, and follow the prompts to create and select a `venv`.
3. **Install development dependencies:**
    ```bash
    pip install -r requirements-dev.txt
    ```
4. The `.vscode/launch.json` provides:
    - `Debugpy: Server` — runs and debugs the server.
    - `Debugpy: Pytest (Current File)` — runs and debugs single test file.
5. The `.vscode/settings.json` configures VS Code to use `pytest` for testing.

## HTTP/HTTPS and DJANGO_DEBUG

- **Production deployments:**
  By default, HTTPS is enforced for security. You should run Django behind a reverse proxy (such as Nginx or Caddy) that handles HTTPS termination.
- **Local development:**
  Set `DJANGO_DEBUG=True` in your `.env` to disable HTTPS enforcement and allow HTTP access at [http://localhost:8000](http://localhost:8000).
- **Docker:**
  The Docker setup respects `DJANGO_DEBUG`. For local testing, set `DJANGO_DEBUG=True` in your `.env`.

**Example .env snippet for local development:**
DJANGO_DEBUG=True STORAGE_BACKEND=local


---

## Troubleshooting

### **Common SSL/HTTP Errors**

- **ERR_SSL_PROTOCOL_ERROR** or browser SSL errors:
  - Cause: The server is enforcing HTTPS, but you are trying to access it via HTTP.
  - **Solution:** Set `DJANGO_DEBUG=True` in your `.env` and restart the server for local development.

- **Cannot access server on HTTP:**
  - Ensure `DJANGO_DEBUG=True` is set in your `.env`.
  - Restart the Django server after changing `.env`.

- **Production deployments:**
  - Always use a reverse proxy (Nginx, Caddy, etc.) to terminate HTTPS and forward requests to Django.
  - Do not set `DJANGO_DEBUG=True` in production.

- **API rate limit:** 100/hour for every users.
- **Static files:** Collected to `/staticfiles` in Docker.
- **Development:** Set `DJANGO_DEBUG=True`.
- **Database:** If empty, will be auto-initialized from GitHub on startup. You can also re-initialize manually with python `manage.py init_db`.

---

## License

FuseSoC is licensed under the permissive 2-clause BSD license, freely allowing use, modification, and distribution of FuseSoC Package Directory for all kinds of projects.

For more details, see the [LICENSE](LICENSE) file.

---

![NLNet logo](https://nlnet.nl/logo/banner.svg)
[This project](https://nlnet.nl/project/FuseSoC-catalog/) was sponsored by [NLNet Foundation](https://nlnet.nl) through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund/)
