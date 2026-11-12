// 생성 화면: 폼을 fetch 로 보내고, 서버의 JSON 응답으로 내려받기 링크를 보여 준다.
function showModal() { document.getElementById('modal-generate').style.display = 'block'; }
function hideModal() { document.getElementById('modal-generate').style.display = 'none'; }

document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('generate-button');
    if (!button) return;
    const loading = document.getElementById('loading-indicator');
    const result = document.getElementById('generated-result');
    const error = document.getElementById('generated-error');
    document.getElementById('modal-close').addEventListener('click', function (e) { e.preventDefault(); hideModal(); });

    button.addEventListener('click', function (e) {
        e.preventDefault();
        const form = document.getElementById('generate-form');
        if (!form.reportValidity()) return;
        showModal();
        loading.style.display = 'block';
        result.style.display = 'none';
        error.style.display = 'none';
        button.disabled = true;

        const formData = new FormData(form);
        fetch('/generator', { method: 'POST', body: formData })
            .then(async (response) => {
                const data = await response.json().catch(() => ({ ok: false, error: response.statusText }));
                if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
                return data;
            })
            .then((data) => {
                loading.style.display = 'none';
                document.getElementById('download-link').href = data.download;
                document.getElementById('spec-link').href = data.spec;
                document.getElementById('result-meta').textContent = data.slides + '장 만들어졌습니다.';
                result.style.display = 'block';
            })
            .catch((err) => {
                loading.style.display = 'none';
                error.textContent = '실패: ' + err.message;
                error.style.display = 'block';
            })
            .finally(() => { button.disabled = false; });
    });
});
