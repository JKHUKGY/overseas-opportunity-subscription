#!/usr/bin/env python3
"""PROTOTYPE: two small public searches + one detail read; never bids or sends mail."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.parse

HERE = Path(__file__).resolve().parent
BASE = 'https://www.freelancer.com/api/projects/0.1/projects/'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def fetch(url):
    # A token, if supplied, goes through stdin rather than a command-line argument.
    token = os.environ.get('FLN_OAUTH_TOKEN', '')
    if any(c in token for c in '\r\n'):
        raise ValueError('令牌不可包含换行')
    config = 'header = "Accept: application/json"\n'
    if token:
        escaped = token.replace('\\', '\\\\').replace('"', '\\"')
        config += 'header = "freelancer-oauth-v1: ' + escaped + '"\n'
    r = subprocess.run(['curl', '--config', '-', '--silent', '--show-error',
                        '--max-time', '20', '--write-out', '\n%{http_code}', url],
                       input=config, capture_output=True, text=True)
    body, _, code = r.stdout.rpartition('\n')
    evidence = {'url': url, 'checked_at': now(), 'http_status': code,
                'credential_present': bool(token), 'transport_error': r.stderr[:300]}
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {}
    evidence['api_status'] = payload.get('status')
    if code != '200' or payload.get('status') != 'success':
        evidence['message'] = str(payload.get('message', '未取得有效项目响应'))[:300]
        return [], evidence
    result = payload.get('result', {})
    return result.get('projects', [result] if 'id' in result else []), evidence


def normalize(project, checked_at, annotations):
    timestamp = project.get('time_submitted') or project.get('submitdate')
    submitted = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat() if isinstance(timestamp, (int, float)) else None
    budget = project.get('budget') or {}
    body = project.get('description') or project.get('preview_description') or ''
    annotation = annotations.get(str(project['id']), {})
    if annotation.get('body_sha256') != hashlib.sha256(body.encode()).hexdigest():
        annotation = {}
    return {'id': str(project['id']), 'source': 'Freelancer',
            'title': project.get('title'),
            'url': 'https://www.freelancer.com/projects/' + project.get('seo_url', ''),
            'published_at': submitted, 'checked_at': checked_at,
            'budget_min': budget.get('minimum'), 'budget_max': budget.get('maximum'),
            'currency': (project.get('currency') or {}).get('code'),
            'pricing': project.get('type'), 'source_status': project.get('status'),
            'frontend_status': project.get('frontend_project_status'),
            'description': body,
            'region': '地域未说明；未核实中国画师申请资格',
            'decision': annotation.get('decision', 'review'),
            'kind': annotation.get('kind', '待判断'),
            'summary': annotation.get('summary', '新发现的项目，等待 AI 阅读正文并生成中文总结。'),
            'reason': annotation.get('reason', '此脚本不调用模型，不会把关键词命中自动认定为绘画需求。'),
            'summary_method': '本次助手逐条阅读生成；不是采集脚本自动生成' if annotation else '未生成',
            'annotation_pending': not bool(annotation)}


def build(snapshot):
    vgen_file = HERE / 'vgen-browser-check.json'
    if vgen_file.exists():
        snapshot['vgen_check'] = json.loads(vgen_file.read_text())
        snapshot['vgen'] = '2026-09-23 Safari 已读到首页、服务、Requested 栏及作品详情；两条具体记录均不属于可申请买方机会。'
    browser_file = HERE / 'browser-sample.json'
    if browser_file.exists():
        snapshot['upwork_sample'] = json.loads(browser_file.read_text())
        snapshot['upwork'] = 'Safari 已读到公开分类列表及 1 条详情（现有会话）；仅相对时间，尚未持续采集。内置浏览器仍不可用。'
    (HERE / 'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    template = (HERE / 'prototype.template.html').read_text()
    encoded = json.dumps(snapshot, ensure_ascii=False).replace('<', '\\u003c')
    (HERE / 'prototype.html').write_text(template.replace('__SNAPSHOT__', encoded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-captured', action='store_true', help='使用本次已取得的响应生成页面，不再次联网')
    args = parser.parse_args()
    annotations = json.loads((HERE / 'annotations.json').read_text())
    records, requests = {}, []
    for query, filename in [('illustration', 'freelancer-curl-response.json'), ('portrait', 'freelancer-portrait.json')]:
        url = BASE + 'active/?' + urllib.parse.urlencode({'query': query, 'limit': 5, 'full_description': 'true'})
        if args.from_captured:
            path = HERE / filename
            payload = json.loads(path.read_text())
            projects = payload.get('result', {}).get('projects', [])
            checked_at = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()
            evidence = {'url': url, 'checked_at': checked_at, 'http_status': '200', 'api_status': payload.get('status'), 'credential_present': False}
        else:
            projects, evidence = fetch(url)
        evidence['returned_count'] = len(projects)
        requests.append(evidence)
        for project in projects:
            records[str(project['id'])] = normalize(project, evidence['checked_at'], annotations)
        if evidence.get('http_status') in ['401', '403', '429']:
            break
    detail_evidence = None
    candidates = [p for p in records.values() if p['decision'] == 'include']
    if candidates:
        selected = next((p for p in candidates if p['id'] == '40725682'), candidates[0])
        url = BASE + selected['id'] + '/?full_description=true'
        if args.from_captured:
            payload = json.loads((HERE / 'freelancer-detail.json').read_text())
            details = [payload.get('result', {})]
            detail_evidence = next(x for x in json.loads((HERE / 'extra-probes.json').read_text()) if x['file'] == 'freelancer-detail.json')
        else:
            details, detail_evidence = fetch(url)
        if details and str(details[0].get('id')) == selected['id']:
            detail = normalize(details[0], detail_evidence['checked_at'], annotations)
            # Existing annotations describe a specific body, not every future revision.
            if detail['description'] != selected['description']:
                detail.update(decision='review', summary='正文在复查时变化，等待重新整理。', annotation_pending=True)
            detail['detail_verified'] = True
            records[selected['id']] = detail
    snapshot = {'generated_at': now(), 'sample_limit_per_query': 5,
                'requests': requests, 'detail_request': detail_evidence,
                'projects': list(records.values()),
                'upwork': '内置浏览器不可用；Safari 补测停在真人验证页，未读到项目；未调用 API',
                'vgen': '已加入测试；公开买方需求入口尚未找到，没有采集结果',
                'scope_note': '少量公开读取，不代表近期总供给、持续稳定性或站外发布授权已验证。'}
    build(snapshot)
    print(f"已生成 {HERE / 'prototype.html'}；真实项目 {len(records)} 条。")
    for r in requests:
        print(f"HTTP {r['http_status']} / {r.get('api_status')} / {r['returned_count']} 条")
    print('中文总结仅对本次已阅读的样本提供；新项目保持待整理。')


if __name__ == '__main__':
    main()
