from pathlib import Path


def test_logs_page_route_exists():
    source = Path("src/web/app.py").read_text(encoding="utf-8")

    assert '@app.get("/logs", response_class=HTMLResponse)' in source
    assert 'return templates.TemplateResponse(request, "logs.html", {"request": request})' in source


def test_template_responses_pass_request_first():
    source = Path("src/web/app.py").read_text(encoding="utf-8")

    assert source.count('templates.TemplateResponse(request,') >= 6
    assert 'templates.TemplateResponse(request, "index.html", {"request": request})' in source
    assert 'templates.TemplateResponse(request, "accounts.html", {"request": request})' in source
    assert 'templates.TemplateResponse(request, "email_services.html", {"request": request})' in source
    assert 'templates.TemplateResponse(request, "settings.html", {"request": request})' in source
    assert 'templates.TemplateResponse(request, "logs.html", {"request": request})' in source
    assert 'templates.TemplateResponse(request, "payment.html", {"request": request})' in source
