function showAddGuidanceForm() {
    const addGuidanceForm = document.getElementById('add-guidance-form');
    if (addGuidanceForm) {
        addGuidanceForm.style.display = 'block';
    }
}

function cancelAddGuidance() {
    const addGuidanceForm = document.getElementById('add-guidance-form');
    if (addGuidanceForm) {
        addGuidanceForm.style.display = 'none';
    }
}

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

function cancelEditGuidance(guidanceId) {
    const editForm = document.getElementById('edit-guidance-' + guidanceId);
    if (editForm) {
        editForm.style.display = 'none';
    }
    const editButton = editForm.previousElementSibling;
    if (editButton) {
        editButton.style.display = 'inline';
    }
    const submitButton = editForm.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.style.display = 'none';
    }
}

function generateAudio(guidanceId, labId) {
    fetch(`/lab/${labId}/generate-audio/${guidanceId}`, {
        method: 'POST'
    }).then(response => {
        if (response.ok) {
            alert('音频生成成功');
            location.reload(true);
        } else {
            alert('音频生成失败');
        }
    });
}

function deleteRecord(guidanceId, labId) {
    if (confirm('确定要删除这条记录吗？')) {
        fetch(`/lab/${labId}/delete-guidance/${guidanceId}`, {
            method: 'POST'
        }).then(response => {
            if (response.ok) {
                alert('记录删除成功');
                // 删除操作成功后，刷新页面或删除页面上的对应元素
                location.reload(true); // 刷新整个页面
            } else {
                alert('记录删除失败');
            }
        });
    }
}