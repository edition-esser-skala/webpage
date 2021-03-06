$(document).ready(function() {
  $('#toctable').dataTable({
    "order": [[ 1, 'asc' ]],
    "autoWidth": false,
    "paging": false,
    "language": {
      "info": "_TOTAL_ works",
      "infoEmpty": "0 works",
      "infoFiltered": "(filtered from _MAX_ total works)",
      "zeroRecords": "(no matching works found)",
      "search": "Filter works:"
    }
  });
} );
