function deleteLab(labId) {
    if (confirm('确定要删除这个实验室及其所有相关记录吗？')) {
        fetch(`/delete-lab/${labId}`, {
            method: 'POST'
        }).then(response => {
            if (response.ok) {
                alert('实验室删除成功');
                location.reload();
            } else {
                alert('实验室删除失败');
            }
        });
    }
}