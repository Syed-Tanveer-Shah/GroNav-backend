document.addEventListener('DOMContentLoaded', function() {
    const branchSelect = document.getElementById('id_branch');
    const detailsSelect = document.getElementById('id_details');
    
    if (branchSelect && detailsSelect) {
        branchSelect.addEventListener('change', function() {
            const branchId = this.value;
            if (branchId) {
                // Use the correct URL pattern we defined
                const url = `/admin/api/branch/${branchId}/categories/`;
                fetch(url)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }
                        return response.json();
                    })
                    .then(data => {
                        // Clear existing options
                        detailsSelect.innerHTML = '';
                        
                        // Add a default empty option
                        const defaultOption = document.createElement('option');
                        defaultOption.value = '';
                        defaultOption.textContent = '---------';
                        detailsSelect.appendChild(defaultOption);
                        
                        // Add new options
                        data.categories.forEach(category => {
                            const option = document.createElement('option');
                            option.value = category.id;
                            option.textContent = category.name;
                            detailsSelect.appendChild(option);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching categories:', error);
                    });
            } else {
                // Clear details if no branch selected
                detailsSelect.innerHTML = '';
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = '---------';
                detailsSelect.appendChild(defaultOption);
            }
        });
        
        // Trigger change event if branch is already selected
        if (branchSelect.value) {
            branchSelect.dispatchEvent(new Event('change'));
        }
    }
});