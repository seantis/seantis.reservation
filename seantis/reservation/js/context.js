if (!this.seantis) this.seantis = {};

// adds a context menu to an event
seantis.contextmenu = function(event, element, calendar) {
    var content = seantis.contextmenu.build(event);
    if (!content) 
        return;
        
    // if the menu only has one possible link it is displayed like a tooltip
    // indicating what action will be executed when the event is clicked
    // (see renderEvent in calendar.js)
    var trigger = seantis.contextmenu.simple(event) ? 'hover' : 'click';
    var delay = trigger === 'hover' ? 200 : 0;
    var aHide = trigger === 'hover' ? false : true;

    // add either overlay or inline loading for the links 
    // depending on the generated content html
    var render_menu = function(element) {
        $.each($('a', element), function(ix, link) {
                var $link = $(link);

                switch ($link.attr('data-target')) {
                    
                    case "overlay":
                        calendar.overlay_init($link);
                        break;

                    case "inpage":
                        var url = $link.attr('href');
                        var filter = '#content';
                        var target = $('#inline-page');
                        calendar.inline_init($link, url, filter, target);
                        break;

                    default:
                        break;
                }
            });
    }

    element.miniTip({
        title: '',
        content: seantis.contextmenu.build(event),
        anchor: 'e',
        delay: delay,
        event: trigger,
        aHide: aHide,
        fadeIn: 100,
        fadeOut: 100,
        render: render_menu
    });  
};

// returns false if the event has more than one menu item
// returns the url of the menu item if there's only one
seantis.contextmenu.simple = function(event) {

    if (event.menuorder.length > 1) 
        return false;

    if (event.menu[event.menuorder[0]].length > 1)
        return false;

    return event.menu[event.menuorder[0]][0].url;    
};

// closes the menu
seantis.contextmenu.close = function() {
    $.fn.miniTip({doHide:true});  
};

// builds the menu html from any object with the following interface
//
// object.menu {
//      <groupname>: [
//          {
//              target: overlay || inpage
//              name:   <some localized name>
//              url:    <some url>
//          }
//      ]
// }
//
// object.menuorder [ order of event.menu <groupnames> ]
//
seantis.contextmenu.build = function(event) {
    var title = _.template('<div><%= text %></div>');
    var entry = _.template('<a class="seantis-reservation-reserve" \
                               data-target="<%= target %>" href="<%= url %>">\
                               <%= name %></a>');

    var simple = seantis.contextmenu.simple(event) !== false;
    
    var html = '';
    for (var i=0; i<event.menuorder.length; i++) {

        var group = event.menuorder[i];
            
        // if there's only a single link the group is not displayed
        if (!simple && group.length > 0)
            html += title({text:group});

        for (var j=0; j<event.menu[group].length; j++) {
            var item = event.menu[group][j];

            html += entry(item);
        }
    }

    return html;
};