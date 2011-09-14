if (!this.seantis) this.seantis = {};

seantis.pad = function (val, len) {
    val = String(val);
    len = len || 2;
    while (val.length < len) val = "0" + val;
        return val;
};

seantis.contextmenu = function(element, content) {
    element.miniTip({
        title: '',
        content: content,
        anchor: 'e',
        event: 'hover',
        aHide: false,
        render: function(element) {
            seantis.calendar.form_overlay($('a', element));
        }
    });  
};