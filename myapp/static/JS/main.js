// 생성 화면: 폼을 fetch 로 보내고, 서버의 JSON 응답으로 내려받기 링크를 보여 준다.
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('generate-form');
    if (!form) return;
    const button = document.getElementById('generate-button');
    const overlay = document.getElementById('modal-generate');
    const loading = document.getElementById('loading-indicator');
    const result = document.getElementById('generated-result');
    const error = document.getElementById('generated-error');
    const closeBtn = document.getElementById('modal-close');
    let busy = false;

    function open() { overlay.classList.add('is-open'); }
    function close() { if (!busy) overlay.classList.remove('is-open'); }
    function show(part) {
        loading.hidden = part !== 'loading';
        result.hidden = part !== 'result';
        error.hidden = part !== 'error';
        closeBtn.hidden = part === 'loading';
    }

    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!form.reportValidity()) return;
        busy = true;
        show('loading');
        open();
        button.disabled = true;

        fetch(form.action, { method: 'POST', body: new FormData(form) })
            .then(async (response) => {
                const data = await response.json().catch(() => ({ ok: false, error: response.statusText }));
                if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
                return data;
            })
            .then((data) => {
                document.getElementById('download-link').href = data.download;
                document.getElementById('spec-link').href = data.spec;
                document.getElementById('result-meta').textContent = data.slides + '장짜리 덱을 만들었습니다.';
                show('result');
            })
            .catch((err) => {
                document.getElementById('error-message').textContent = err.message;
                show('error');
            })
            .finally(() => { busy = false; button.disabled = false; });
    });
});
