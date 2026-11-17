// 생성 화면: 폼을 보내 작업을 시작하고, /jobs/<id> 를 2초마다 물어 진행률을 보여 준다.
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('generate-form');
    if (!form) return;
    const button = document.getElementById('generate-button');
    const overlay = document.getElementById('modal-generate');
    const loading = document.getElementById('loading-indicator');
    const result = document.getElementById('generated-result');
    const error = document.getElementById('generated-error');
    const closeBtn = document.getElementById('modal-close');
    const stageEl = document.getElementById('progress-stage');
    const countEl = document.getElementById('progress-count');
    const bar = document.getElementById('progress-bar');
    let busy = false;

    function open() { overlay.classList.add('is-open'); }
    function close() { if (!busy) overlay.classList.remove('is-open'); }
    function show(part) {
        loading.hidden = part !== 'loading';
        result.hidden = part !== 'result';
        error.hidden = part !== 'error';
        closeBtn.hidden = part === 'loading';
    }
    function fail(message) {
        document.getElementById('error-message').textContent = message;
        show('error');
        busy = false;
        button.disabled = false;
    }
    function minutes(sec) {
        const m = Math.floor(sec / 60), s = sec % 60;
        return m ? m + '분 ' + s + '초' : s + '초';
    }

    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    window.addEventListener('beforeunload', function (e) { if (busy) { e.preventDefault(); e.returnValue = ''; } });

    function poll(url) {
        fetch(url)
            .then((r) => r.json())
            .then((job) => {
                if (!job.ok) return fail(job.error || '작업 상태를 읽지 못했습니다.');
                if (job.state === 'error') return fail(job.error);
                if (job.state === 'done') {
                    document.getElementById('download-link').href = job.download;
                    document.getElementById('spec-link').href = job.spec;
                    document.getElementById('result-meta').textContent =
                        job.slides + '장짜리 덱을 만들었습니다. 걸린 시간 ' + minutes(job.elapsed) + '.';
                    show('result');
                    busy = false;
                    button.disabled = false;
                    return;
                }
                const total = job.total || 1;
                const pct = job.stage === '개요 짜는 중' ? 8 : job.stage === '파일 만드는 중' ? 95
                    : 10 + Math.round(80 * (job.done || 0) / total);
                bar.style.width = Math.max(3, Math.min(pct, 97)) + '%';
                stageEl.textContent = job.stage;
                countEl.textContent = (job.stage === '장 쓰는 중' ? job.done + ' / ' + total + '장 · ' : '')
                    + '지난 시간 ' + minutes(job.elapsed);
                setTimeout(() => poll(url), 2000);
            })
            .catch(() => setTimeout(() => poll(url), 4000));
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!form.reportValidity()) return;
        busy = true;
        bar.style.width = '3%';
        stageEl.textContent = '시작하는 중';
        countEl.textContent = '창을 닫지 마세요. 큰 덱은 몇 분 걸립니다.';
        show('loading');
        open();
        button.disabled = true;

        fetch(form.action, { method: 'POST', body: new FormData(form) })
            .then(async (response) => {
                const data = await response.json().catch(() => ({ ok: false, error: response.statusText }));
                if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
                poll(data.status);
            })
            .catch((err) => fail(err.message));
    });
});
