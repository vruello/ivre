#! /usr/bin/env python

# This file is part of IVRE.
# Copyright 2011 - 2018 Pierre LALET <pierre.lalet@cea.fr>
#
# IVRE is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IVRE is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with IVRE. If not, see <http://www.gnu.org/licenses/>.

"""
Access and query the flows database.

See doc/FLOW.md for more information.
"""
from __future__ import print_function
import datetime
import os
import sys
try:
    reload(sys)
except NameError:
    pass
else:
    sys.setdefaultencoding('utf-8')


from builtins import input
from future.utils import viewitems
try:
    import matplotlib
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


from ivre.db import db
from ivre import utils, config


def main():
    parser, _ = utils.create_argparser(__doc__)
    parser.add_argument('--init', '--purgedb', action='store_true',
                        help='Purge or create and initialize the database.')
    parser.add_argument('--ensure-indexes', action='store_true',
                        help='Create missing indexes (will lock the '
                        'database).')
    parser.add_argument('--node-filters', '-n', nargs="+", metavar="FILTER",
                        help='Filter the results with a list of ivre specific '
                        'node textual filters (see WebUI doc in FLOW.md).')
    parser.add_argument('--flow-filters', '-f', nargs="+", metavar="FILTER",
                        help='Filter the results with a list of ivre specific '
                        'flow textual filters (see WebUI doc in FLOW.md).')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Outputs the full json records of results.')
    parser.add_argument('--count', '-c', action='store_true',
                        help='Only return the count of the results.')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Ouput at most LIMIT results.')
    parser.add_argument('--skip', type=int, default=0,
                        help='Skip first SKIP results.')
    parser.add_argument('--orderby', '-o',
                        help='Order of results ("src", "dst" or "flow")')
    parser.add_argument('--separator', '-s', help="Separator string.")
    parser.add_argument('--top', '-t', nargs="+",
                        help='Top flows for a given set of fields, e.g. '
                        '"--top src.addr dport".')
    parser.add_argument('--collect', '-C', nargs="+",
                        help='When using --top, also collect these '
                        'properties.', default=[])
    parser.add_argument('--sum', '-S', nargs="+",
                        help='When using --top, sum on these properties to '
                        'order the result.', default=[])
    parser.add_argument('--least', '-L', action='store_true',
                        help='When using --top, sort records by least')
    parser.add_argument('--mode', '-m',
                        help="Query special mode (flow_map, talk_map...)")
    parser.add_argument('--timeline', '-T', action="store_true",
                        help='Retrieves the timeline of each flow')
    parser.add_argument('--flow-daily', action="store_true",
                        help="Flow count per times of the day. If --precision "
                        "is absent, it will be based on FLOW_TIME_PRECISION "
                        "(%d)" % config.FLOW_TIME_PRECISION)
    parser.add_argument('--plot', action="store_true",
                        help="Plot data when possible (requires matplotlib).")
    parser.add_argument('--fields', nargs='+',
                        help="Display these fields for each entry.")
    parser.add_argument('--reduce-precision', type=int,
                        metavar="NEW_PRECISION",
                        help="Only with MongoDB backend. "
                        "Reduce precision to NEW_PRECISION for flows "
                        "timeslots. Takes account of precision, before, "
                        "after, filters.")
    parser.add_argument("--base", "-B", type=int, help="Only with MongoDB "
                        "backend. When using --reduce-precision, set timeslots"
                        " base. Defaults to " + str(config.FLOW_DEFAULT_BASE),
                        default=None)
    parser.add_argument("--after", "-a", type=str, help="Only with MongoDB "
                        "backend. Get only flows seen after this date. "
                        "Date format: YEAR-MONTH-DAY HOUR:MINUTE. "
                        "Based on timeslots precision.")
    parser.add_argument("--before", "-b", type=str, help="Only with MongoDB "
                        "backend. Get only flows seen before this date. "
                        "Date format: YEAR-MONTH-DAY HOUR:MINUTE. "
                        "Based on timeslots precision.")
    parser.add_argument('--precision', nargs='?', default=None, const=0,
                        help="Only With MongoDB backend. If PRECISION is "
                        "specified, get only flows with one timeslot of"
                        "the given precision. Otherwise, list "
                        "precisions.", type=int)
    args = parser.parse_args()

    out = sys.stdout

    if args.plot and plt is None:
        utils.LOGGER.critical("Matplotlib is required for --plot")
        sys.exit(-1)

    if args.init:
        if os.isatty(sys.stdin.fileno()):
            out.write(
                'This will remove any flow result in your database. '
                'Process ? [y/N] ')
            ans = input()
            if ans.lower() != 'y':
                sys.exit(-1)
        db.flow.init()
        sys.exit(0)

    if args.ensure_indexes:
        if os.isatty(sys.stdin.fileno()):
            out.write(
                'This will lock your database. '
                'Process ? [y/N] ')
            ans = input()
            if ans.lower() != 'y':
                sys.exit(-1)
        db.flow.ensure_indexes()
        sys.exit(0)

    if args.precision == 0:
        # Get precisions list
        for precision in db.flow.list_precisions():
            out.write('%d\n' % precision)
        sys.exit(0)

    filters = {"nodes": args.node_filters or [],
               "edges": args.flow_filters or []}

    time_args = ['before', 'after']
    time_values = {}
    args_dict = vars(args)
    for arg in time_args:
        time_values[arg] = (
            datetime.datetime.strptime(args_dict[arg], "%Y-%m-%d %H:%M")
            if args_dict[arg] is not None
            else None)

    query = db.flow.from_filters(filters, limit=args.limit, skip=args.skip,
                                 orderby=args.orderby, mode=args.mode,
                                 timeline=args.timeline,
                                 after=time_values['after'],
                                 before=time_values['before'],
                                 precision=args.precision)

    if args.reduce_precision:
        if os.isatty(sys.stdin.fileno()):
            out.write(
                'This will permanently reduce the precision of your '
                'database. Process ? [y/N] ')
            ans = input()
            if ans.lower() != 'y':
                sys.exit(-1)
        new_duration = args.reduce_precision
        db.flow.reduce_precision(new_duration, flt=query,
                                 base=args.base, before=time_values['before'],
                                 after=time_values['after'],
                                 precision=args.precision)
        sys.exit(0)

    sep = args.separator or ' | '
    coma = ' ;' if args.separator else ' ; '
    coma2 = ',' if args.separator else ', '
    if args.count:
        count = db.flow.count(query,
                              after=time_values['after'],
                              before=time_values['before'],
                              precision=args.precision)
        out.write('%(clients)d clients\n%(servers)d servers\n'
                  '%(flows)d flows\n' % count)

    elif args.top:
        top = db.flow.topvalues(query, args.top, collect_fields=args.collect,
                                sum_fields=args.sum, topnbr=args.limit,
                                skip=args.skip, least=args.least)
        for rec in top:
            sys.stdout.write("%s%s%s%s%s\n" % (
                '(' + coma2.join(str(val) for val in rec["fields"]) + ')',
                sep,
                rec["count"],
                sep,
                coma.join(str('(' +
                              coma2.join(str(val) for val in collected) +
                              ')')
                          for collected in rec["collected"])
                if rec["collected"] else ""
            ))

    elif args.flow_daily:
        precision = (args.precision if args.precision is not None
                     else config.FLOW_TIME_PRECISION)
        plot_data = {}
        for rec in db.flow.flow_daily(precision, flt=query):
            out.write(
                sep.join([
                    rec["time_in_day"].strftime("%T.%f"),
                    " ; ".join(['(' + x[0] + ', ' + str(x[1]) + ')'
                                for x in rec["flows"]])]))
            out.write("\n")

            if args.plot:
                for flw in rec["flows"]:
                    plot_data.setdefault(flw[0], [[], []])
                    plot_data[flw[0]][0].append(rec["time_in_day"])
                    plot_data[flw[0]][1].append(flw[1])
        if args.plot:
            ax = plt.subplots()[1]
            fmt = matplotlib.dates.DateFormatter('%H:%M:%S')
            for flow, points in viewitems(plot_data):
                plt.plot(points[0], points[1], label=flow, marker='o')
            plt.legend(loc='best')
            ax.xaxis.set_major_formatter(fmt)
            plt.show()

    else:
        fmt = '%%s%s%%s%s%%s' % (sep, sep)
        node_width = len('XXXX:XXXX:XXXX:XXXX:XXXX:XXXX')
        flow_width = len('tcp/XXXXX')
        for res in db.flow.to_iter(query, limit=args.limit, skip=args.skip,
                                   orderby=args.orderby, mode=args.mode,
                                   timeline=args.timeline):
            if args.json:
                out.write('%s\n' % res)
            else:
                elts = {}
                for elt in ["src", "flow", "dst"]:
                    elts[elt] = res[elt]['label']
                    if args.fields:
                        elts[elt] = "%s%s%s" % (
                            elts[elt],
                            coma,
                            coma.join(
                                str(res[elt]['data'].get(field, ""))
                                for field in args.fields
                            )
                        )
                src, flow, dst = elts["src"], elts["flow"], elts["dst"]
                node_width = max(node_width, len(src), len(dst))
                flow_width = max(flow_width, len(flow))
                if not args.separator:
                    fmt = ('%%-%ds%s%%-%ds%s%%-%ds' %
                           (node_width, sep, flow_width, sep, node_width))
                out.write(fmt % (src, flow, dst))
                if args.timeline:
                    out.write(sep)
                    # Print '?' instead of failing if meta.times does not exist
                    try:
                        out.write(coma.join(
                            str(elt) for elt in sorted(
                                res['flow']['data']['meta']['times']
                            )
                        ))
                    except KeyError:
                        out.write("?")
                out.write('\n')
