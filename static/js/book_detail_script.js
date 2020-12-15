$(document).ready(function () {
    var maxHeight = 0;
    $("h2.header").each(function () {
        if ($(this).height() > maxHeight) {
            maxHeight = $(this).height();
        }
    });
    $("h2.header").height(maxHeight);
})