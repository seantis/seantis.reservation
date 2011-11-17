if (!this.seantis) this.seantis = {};

// Adds the contextmenu to the element and adds plone overlays to all
// links in the content
seantis.contextmenu = function(event, element, calendar) {
    var content = seantis.contextmenu.build(event);
    if (!content)
        return;
        
    var inline = $('#inline-page');
    var trigger = seantis.contextmenu.simple(event) ? 'hover' : 'click';
    var delay = trigger === 'hover' ? 200 : 0;
    var aHide = trigger === 'hover' ? false : true;

    element.miniTip({
        title: '',
        content: seantis.contextmenu.build(event),
        anchor: 'e',
        delay: delay,
        event: trigger,
        aHide: aHide,
        fadeIn: 100,
        fadeOut: 100,
        render: function(element) {
            $.each($('a', element), function(ix, link) {
                var $link = $(link);

                var target = $link.attr('data-target');
                switch (target) {
                    
                    case "overlay":
                        calendar.overlay_init($link);
                        break;

                    case "inpage":
                        var url = $link.attr('href');
                        calendar.inline_init($link, url, '#content', inline);
                        break;

                    default:
                        break;
                }
            });
        }
    });  
};

seantis.contextmenu.simple = function(event) {
    if (event.menuorder.length > 1) 
        return false;

    if (event.menu[event.menuorder[0]].length > 1)
        return false;

    return event.menu[event.menuorder[0]][0].url;    
};

seantis.contextmenu.close = function() {
    $.fn.miniTip({doHide:true});  
};

seantis.contextmenu.build = function(event) {
    var title = _.template('<div><%= text %></div>');
    var entry = _.template('<a class="seantis-reservation-reserve" \
                               data-target="<%= target %>" href="<%= url %>">\
                               <%= name %></a>');

    var simple = seantis.contextmenu.simple(event);
    
    var html = '';
    for (var i=0; i<event.menuorder.length; i++) {

        var group = event.menuorder[i];
        
        if (!simple && group.length > 0)
            html += title({text:group});

        for (var j=0; j<event.menu[group].length; j++) {
            var item = event.menu[group][j];

            html += entry(item);
        }
    }

    return html;
};