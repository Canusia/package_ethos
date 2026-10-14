/* Banner Grade Push setting: Look up a sample registration and fill the GUIDs.
 * Loaded by the setting form's layout inside the settings Edit modal. */
(function ($) {
  var $root = $('#grade-push-settings');
  if (!$root.length || $root.data('ready')) { return; }
  $root.data('ready', true);

  var $form = $root.closest('form');
  var $reg = $form.find('[name=sample_registration]');
  var $type = $form.find('[name=final_grade_type]');
  var $map = $form.find('[name=grade_map]');
  var $by = $form.find('[name=grade_submitted_by]');
  var $source = $form.find('[name=submitted_by_source]');
  var $byGroup = $by.closest('.form-group');

  // The GUID is used only for "This Banner person".
  function toggleBy() {
    $byGroup.toggle($source.filter(':checked').val() === 'person');
  }
  $source.on('change', toggleBy);
  toggleBy();
  var url = $root.data('lookup-url');

  var $btn = $('<button type="button" class="btn btn-sm btn-outline-primary mt-1">Look up</button>');
  var $status = $('<div class="small mt-1"></div>');
  $reg.after($status).after($btn);

  function readMap() {
    try { var m = JSON.parse($map.val() || '{}'); return (m && typeof m === 'object') ? m : {}; }
    catch (e) { return {}; }
  }
  function esc(s) { return $('<div>').text(s == null ? '' : String(s)).html(); }

  function fillType(types, current) {
    $type.nextAll('.gp-type').remove();
    if (!types.length) {
      // Nothing to choose from: keep the plain field so the saved value survives.
      $type.show();
      return ' Banner returned no grade types; enter the Final Grade Type GUID by hand.';
    }
    var has = function (id) { return types.some(function (t) { return t.id === id; }); };
    var final = types.filter(function (t) { return t.code === 'FINAL'; })[0];
    var pick = (current && has(current)) ? current : (final ? final.id : types[0].id);
    var $sel = $('<select class="form-control"></select>');
    types.forEach(function (t) {
      $sel.append($('<option>').val(t.id).text(t.code + ' \u2014 ' + t.title));
    });
    $sel.val(pick);
    $type.val(pick).hide();
    $sel.addClass('gp-type').insertAfter($type).on('change', function () { $type.val(this.value); });
    return '';
  }

  function fillMap(scale, options, current) {
    var byValue = {}; var ids = {};
    options.forEach(function (o) { byValue[o.value] = o.id; ids[o.id] = o.value; });
    var letters = scale.length ? scale : Object.keys(current);
    var $table = $('<table class="table table-sm gp-map"><tbody></tbody></table>');
    letters.forEach(function (letter) {
      var $sel = $('<select class="form-control form-control-sm"><option value="">— not mapped —</option></select>')
        .attr('data-letter', letter);
      options.forEach(function (o) { $sel.append($('<option>').val(o.id).text(o.value)); });
      $sel.val(current[letter] && ids[current[letter]] ? current[letter] : (byValue[letter] || ''));
      var $flag = $('<span class="text-danger small ml-2"></span>');
      $table.find('tbody').append($('<tr>').append($('<td>').text(letter)).append($('<td>').append($sel)).append($('<td>').append($flag)));
    });
    $map.hide().nextAll('.gp-map').remove();
    $table.insertAfter($map);
    function sync() {
      var out = {};
      $table.find('select').each(function () {
        var $s = $(this);
        $s.closest('tr').find('span').text($s.val() ? '' : 'not mapped');
        if ($s.val()) { out[$s.data('letter')] = $s.val(); }
      });
      $map.val(JSON.stringify(out, null, 2));
    }
    $table.on('change', 'select', sync);
    sync();
  }

  function fillInstructors(instructors) {
    $form.find('.gp-by').remove();
    if (!instructors.length) { return; }
    var $wrap = $('<div class="gp-by mt-1 small">Section instructors (click to use as a fixed person): </div>');
    instructors.forEach(function (i) {
      $('<button type="button" class="btn btn-link btn-sm p-0 mr-2"></button>')
        .text(i.name + (i.role ? ' (' + i.role + ')' : ''))
        .on('click', function () {
          $by.val(i.id);
          $source.filter('[value=person]').prop('checked', true);
          toggleBy();
        })
        .appendTo($wrap);
    });
    $wrap.insertAfter($source.last().closest('.form-group'));
  }

  $btn.on('click', function () {
    $status.removeClass('text-danger text-warning').text('Looking up…');
    $.getJSON(url, { registration: $reg.val() })
      .done(function (data) {
        var current = readMap();
        var optionIds = data.grade_options.map(function (o) { return o.id; });
        var foreign = Object.keys(current).filter(function (k) { return optionIds.indexOf(current[k]) === -1; });
        var typeNote = fillType(data.grade_types, data.current.final_grade_type);
        fillMap(data.scale, data.grade_options, current);
        fillInstructors(data.instructors);
        var msg = 'Grade scheme: ' + esc(data.scheme.title || data.scheme.id);
        if (foreign.length) {
          $status.addClass('text-warning');
          msg += '. The saved map has grades that are not options of this registration ('
            + esc(foreign.join(', ')) + '); they were re-matched by letter.';
        }
        if (typeNote) { $status.addClass('text-warning'); msg += '.' + esc(typeNote); }
        $status.html(msg);
      })
      .fail(function (xhr) {
        var body = xhr.responseJSON || {};
        var msg = esc(body.error || ('Look up failed (HTTP ' + xhr.status + ').'));
        if (body.log_url) { msg += ' <a href="' + esc(body.log_url) + '" target="_blank">View log</a>'; }
        $status.addClass('text-danger').html(msg);
      });
  });
})(window.jQuery);
