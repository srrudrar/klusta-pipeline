
import os
import glob
from pprint import pformat
from string import Template
from shutil import copyfile
import h5py as h5
from klusta_pipeline import MAX_CHANS, TEMPLATE_DIR
from klusta_pipeline.utils import chunkit, get_info
from klusta_pipeline.probe import get_channel_groups, clean_dead_channels, build_geometries

try: import simplejson as json
except ImportError: import json

def parse_catlog_line(line):
    '''
    Parses one line in the catlog file to return a tuple of parameters.

    Parameters
    ----------
    line : string
        One `line` in the catlog file.

    Returns
    -------
    smrx : str
        Description of anonymous integer return value.
    duration : float
        Length of the file in seconds.
    mb : float
        Size of the file in Mb.
    nchan : int
        Number of recorded channels.
    '''
    file_info = line.strip().split(',')
    smrx = file_info[0].strip('"')
    duration  = float(file_info[1])
    mb = float(file_info[3])
    nchan = int(file_info[5])
    return smrx,duration,mb,nchan

def read_catlog(f):
    '''
    Reads the catlog file handler to yield export info.

    Parameters
    ----------
    f : int
        File handler

    Returns
    -------
    exports : list
        List of dicts containing parameters for each of the lines in the catlog file.
    '''
    exports = []
    for line in f:
        smrx,duration,mb,nchan = parse_catlog_line(line)
        d = get_info(smrx)
        d.update(
            smrx=smrx,
            duration=duration,
            mb=mb,
            n_chan=nchan,
        )
        exports.append(d)
    return exports

def load_catlog(catlog):
    '''
    Reads the catlog file and returns export info.

    Parameters
    ----------
    catlog : str
        String containing path of catlog file.

    Returns
    -------
    exports : list
        List of dicts containing parameters for each of the lines in the catlog file.
    '''
    with open(catlog,'r') as f:
        exports = read_catlog(f)
    return exports

def read_recordings(f,chans):
    s2mat_recordings = []
    for ch in chans:
        chan_data = f[ch]
        times = chan_data['times'][0]
        values = chan_data['values'][0]
        fs = 1.0 / chan_data['interval'][0]
        for ii, (t,v) in enumerate(chunkit(times,values)):
            d = {ch: {'times':t,'values':v,'fs':fs}}
            try:
                s2mat_recordings[ii].update(d)
            except IndexError:
                print ' rec %i (%0.2f seconds long)' % (ii,t[-1]-t[0])
                s2mat_recordings.append(d)
        print '  %s' % ch
    return s2mat_recordings

def load_recordings(s2mat,chans):
    recordings = []
    print 'Loading %s' % s2mat
    with h5.File(s2mat, 'r') as f:
        recs = read_recordings(f,chans)
        for r in recs:
            r.update(file_origin=s2mat)
        recordings += recs
    return recordings

def save_recording(kwd,rec,index):
    with h5.File(kwd, 'a') as kwd_f:
        print ' saving recordings/%i/data...' % index
        kwd_f.create_dataset('recordings/%i/data' % index, data=rec['data'])
        print ' saved!'

def save_chanlist(kwd_dir,chans,port_map):
    chanfile = os.path.join(kwd_dir,'indx_port_site.txt')
    with open(chanfile,'w') as f:
        for ch,port in enumerate(chans):
            f.write("%i,%s,%i\n" % (ch,port,port_map[port]))
    print 'chans saved to %s' % chanfile

def save_probe(probe,chans,port_map,export):

    s = {site+1:None for site in range(MAX_CHANS)}
    for ch,port in enumerate(chans):
        site = port_map[port]
        s[site] = ch

    channel_groups = get_channel_groups(probe,s)
    channel_groups = clean_dead_channels(channel_groups)
    channel_groups = build_geometries(channel_groups)

    with open(os.path.join(export,probe+'.prb'), 'w') as f:
        f.write('channel_groups = ' + pformat(channel_groups))

def save_parameters(params,export):
    # read the parameters template
    params_template_in = os.path.join(TEMPLATE_DIR,'params.template')
    with open(params_template_in,'r') as src:
        params_template = Template(src.read())

    # write the parameters
    with open(os.path.join(export,'params.prm'), 'w') as pf:
        pf.write(params_template.substitute(params))

def save_info(path,info):
    name = info['name']
    with open(os.path.join(path,name+'_info.json'),'w') as f:
        json.dump(info,f,indent=4,sort_keys=True)
