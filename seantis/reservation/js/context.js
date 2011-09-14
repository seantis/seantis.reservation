if (!this.seantis) this.seantis = {};

seantis.pad = function (val, len) {
    val = String(val);
    len = len || 2;
    while (val.length < len) val = "0" + val;
        return val;
};

seantis.eventRender = function(event, element) {
    var reserve = '<a href="' + event.url + '">'
    reserve += seantis.locale('reserve') + '</a>';

    element.miniTip({
        title: '',
        content: reserve,
        anchor: 'e',
        event: 'hover',
        aHide: false
    });
};