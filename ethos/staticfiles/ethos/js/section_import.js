function triggerSectionImport(recordId) {
    $.blockUI({ message: '<h4>Importing sections from SIS&hellip;</h4>' });

    $.post(sectionImportUrl, {
        'record_id': recordId,
        'csrfmiddlewaretoken': csrfToken
    })
    .done(function(data) {
        if (data.task_id) {
            pollSectionImportStatus(data.task_id);
        } else {
            $.unblockUI();
            swal('Error', data.message || 'Failed to start import.', 'error');
        }
    })
    .fail(function() {
        $.unblockUI();
        swal('Error', 'Failed to start import.', 'error');
    });
}

function pollSectionImportStatus(taskId) {
    var interval = setInterval(function() {
        $.get(sectionImportStatusUrl, { task_id: taskId })
        .done(function(data) {
            if (data.status === 'SUCCEEDED') {
                clearInterval(interval);
                $.unblockUI();
                var c = data.counts || {};
                var total = c.total_fetched !== undefined ? c.total_fetched : '?';
                var created = c.section_created !== undefined ? c.section_created : '?';
                var updated = c.section_updated !== undefined ? c.section_updated : '?';
                var skipped = c.section_skipped !== undefined ? c.section_skipped : '?';
                swal(
                    'Import Complete',
                    total + ' sections fetched\nCreated: ' + created + '  Updated: ' + updated + '  Skipped: ' + skipped,
                    'success'
                );
            } else if (data.status === 'FAILED') {
                clearInterval(interval);
                $.unblockUI();
                swal('Import Failed', data.error || 'An error occurred during import.', 'error');
            }
            // else still QUEUED/RUNNING — keep polling
        })
        .fail(function() {
            clearInterval(interval);
            $.unblockUI();
            swal('Error', 'Lost connection while polling for status.', 'error');
        });
    }, 3000);
}
