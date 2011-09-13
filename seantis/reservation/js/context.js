if (!this.seantis) this.seantis = {};

seantis.pad = function (val, len) {
    val = String(val);
    len = len || 2;
    while (val.length < len) val = "0" + val;
        return val;
};

seantis.eventRender = function(event, element) {
    var title = '';
    title += seantis.pad(event.start.getDay()) + '.';
    title += seantis.pad(event.start.getMonth() + 1) + '.';
    title += event.start.getFullYear() + '&nbsp;';
    title += seantis.pad(event.start.getHours()) + ':';
    title += seantis.pad(event.start.getMinutes()) + '&nbsp;-&nbsp;';
    title += seantis.pad(event.end.getHours()) + ':';
    title += seantis.pad(event.end.getMinutes());

    var reserve = '<a href="' + event.url + '">'
    reserve += seantis.locale('reserve') + '</a>';

    element.miniTip({
        title: title,
        content: reserve,
        anchor: 'e',
        event: 'hover',
        aHide: false
    });
};