if (!this.seantis) this.seantis = {};

// Adds the contextmenu to the element and adds plone overlays to all
// links in the content
seantis.contextmenu = function(event, element, calendar) {
    element.miniTip({
        title: '',
        content: seantis.contextmenu.build(event),
        anchor: 'e',
        event: 'hover',
        aHide: false,
        fadeIn: 100,
        render: function(element) {
            calendar.overlay_init($('a', element));
        }
    });  
};

seantis.contextmenu.build = function(event) {
    var title = _.template('<div><%= text %></div>');
    var entry = _.template('<a class="seantis-reservation-reserve" href="<%= url %>"><%= text %></a>');
    var locale = seantis.locale;
    var html = '';

    var single = [
        title({text: locale('entry')}),
        entry({text: locale('reserve'), url:event.url}),
        entry({text: locale('edit'),    url:event.editurl}),
        entry({text: locale('remove'),  url:event.removeurl})
    ];

    html = single.join('');

    if (event.groupurl) {
        var group = [
            title({text: locale('group')}),
            entry({text: locale('showgroup'), url:   event.groupurl}),
            entry({text: locale('removegroup'), url: event.removegroupurl})
        ];    

        html += group.join('');
    }

    return html;
};