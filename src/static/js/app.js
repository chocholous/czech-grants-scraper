/**
 * Client-side filtering for Czech Grants UI
 */

// DOM elements
const searchInput = document.getElementById('searchInput');
const sourceFilter = document.getElementById('sourceFilter');
const statusFilter = document.getElementById('statusFilter');
const activeOnlyFilter = document.getElementById('activeOnlyFilter');
const grantRows = document.querySelectorAll('.grant-row');
const visibleCount = document.getElementById('visibleCount');
const noResultsMessage = document.getElementById('noResultsMessage');

/**
 * Main filter function - applies ALL filter criteria
 */
function filterGrants() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const sourceId = sourceFilter.value;
    const statusValue = statusFilter.value;
    const activeOnly = activeOnlyFilter.checked;

    let visibleGrantsCount = 0;

    grantRows.forEach(row => {
        // Extract data attributes
        const rowSourceId = row.dataset.sourceId || '';
        const rowTitle = row.dataset.title || '';
        const rowDescription = row.dataset.description || '';
        const rowStatus = row.dataset.status || '';
        const rowActive = row.dataset.active === 'true';

        // Apply filters
        const matchesSource = !sourceId || rowSourceId === sourceId;
        const matchesSearch = !searchTerm ||
                              rowTitle.includes(searchTerm) ||
                              rowDescription.includes(searchTerm);
        const matchesStatus = !statusValue || rowStatus === statusValue;
        const matchesActive = !activeOnly || rowActive;

        // Show/hide row based on all criteria
        if (matchesSource && matchesSearch && matchesStatus && matchesActive) {
            row.style.display = '';
            visibleGrantsCount++;
        } else {
            row.style.display = 'none';
        }
    });

    // Update visible count badge
    visibleCount.textContent = visibleGrantsCount;

    // Show/hide "no results" message
    if (visibleGrantsCount === 0) {
        noResultsMessage.style.display = 'block';
    } else {
        noResultsMessage.style.display = 'none';
    }
}

/**
 * Debounce function for search input
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Debounced search handler
const debouncedFilter = debounce(filterGrants, 300);

// Event listeners
searchInput.addEventListener('input', debouncedFilter);
sourceFilter.addEventListener('change', filterGrants);
statusFilter.addEventListener('change', filterGrants);
activeOnlyFilter.addEventListener('change', filterGrants);

// Initial filter on page load (in case filters are pre-selected)
document.addEventListener('DOMContentLoaded', filterGrants);
