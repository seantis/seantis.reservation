if (!this.seantis) this.seantis = {};
if (!this.seantis.utils) this.seantis.utils = {};

seantis.utils.parse_date = function(isodate) {
    var parse = function(str) { return parseInt(str, 10); };
    var values = _.map(isodate.split('-'), parse);

    return {year:values[0], month:values[1], day:values[2]};
};