document.addEventListener('DOMContentLoaded', function() {
    // 显示添加讲解内容的表单
    const addGuidanceButton = document.getElementById('add-guidance-button');
    const addGuidanceForm = document.getElementById('add-guidance-form');
    if (addGuidanceButton && addGuidanceForm) {
        addGuidanceButton.addEventListener('click', function() {
            addGuidanceForm.style.display = 'block';
        });
    }

    // 处理每个讲解内容的修改按钮
    document.querySelectorAll('button[data-action="edit"]').forEach(function(button) {
        button.addEventListener('click', function() {
            const guidanceId = this.dataset.guidanceId;
            const editForm = document.getElementById('edit-guidance-' + guidanceId);
            if (editForm) {
                // 显示对应的修改表单
                editForm.style.display = 'block';
                // 隐藏当前的修改按钮
                this.style.display = 'none';
                // 显示提交按钮
                const submitButton = editForm.querySelector('button[type="submit"]');
                if (submitButton) {
                    submitButton.style.display = 'inline';
                }
            }
        });
    });
});

// 定义 editGuidance 函数，以便可以在 HTML 中直接调用
function editGuidance(guidanceId) {
    const editForm = document.getElementById('edit-guidance-' + guidanceId);
    if (editForm) {
        editForm.style.display = 'block';
        const editButton = editForm.previousElementSibling;
        if (editButton) {
            editButton.style.display = 'none';
        }
        const submitButton = editForm.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.style.display = 'inline';
        }
    }
}

function generateAudio(guidanceId, labId) {
    fetch(`/lab/${labId}/generate-audio/${guidanceId}`, {
        method: 'POST'
    }).then(response => {
        if (response.ok) {
            alert('音频生成成功');
            location.reload();
        } else {
            alert('音频生成失败');
        }
    });
}
