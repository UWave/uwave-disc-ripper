"""Various celery tasks"""
import fakemtx as mtx
import audiotools
from audiotools.ui import process_output_options
from audiotools import accuraterip
from audiotools.cdio import CDDAReader
from celerymaker import make_celery
from celery.exceptions import Ignore
from flask import Flask
import config


PREVIOUS_TRACK_FRAMES = (5880 // 2)
NEXT_TRACK_FRAMES = (5880 // 2)

app = Flask(__name__)
config.configure(app)
msg = audiotools.SilentMessenger()

CELERY_ROUTES = {
    "tasks.ripdisk": "cdrom",
    "tasks.mtx": "changer"
}

celery = make_celery(app)
changer = mtx.Changer(app.config['ripper']['changer'])


class AccurateRipReader(object):
    def __init__(self, pcmreader, total_pcm_frames, is_first, is_last):
        """pcmreader is a PCMReader object to wrap around
        total_pcm_frames is the length of pcmreader,
        not including previous and next track frames
        is_first and is_last indicate the track's position in the stream"""

        self.pcmreader = pcmreader

        self.checksummer = accuraterip.Checksum(
            total_pcm_frames=total_pcm_frames,
            sample_rate=pcmreader.sample_rate,
            is_first=is_first,
            is_last=is_last,
            pcm_frame_range=PREVIOUS_TRACK_FRAMES + 1 + NEXT_TRACK_FRAMES,
            accurateripv2_offset=PREVIOUS_TRACK_FRAMES)

        self.sample_rate = pcmreader.sample_rate
        self.channels = pcmreader.channels
        self.channel_mask = pcmreader.channel_mask
        self.bits_per_sample = pcmreader.bits_per_sample

    def read(self, pcm_frames):
        frame = self.pcmreader.read(pcm_frames)
        self.checksummer.update(frame)
        return frame

    def close(self):
        self.pcmreader.close()

    def checksums_v1(self):
        return self.checksummer.checksums_v1()

    def checksums_v2(self):
        return [self.checksummer.checksum_v2()]


class CeleryProgressDisplay(audiotools.ProgressDisplay):
    """A ProgressDisplay class to send status updates via celery's update_state"""
    def __init__(self, messenger, metadata, celery_task):
        audiotools.ProgressDisplay.__init__(self, messenger)
        self.metadata = metadata
        self.celery_task = celery_task

    def update(self, progress):
        """updates the celery state with new progress value"""
        metadata = self.metadata
        metadata['progress'] = progress.numerator/progress.denominator
        self.celery_task.update_state(state='PROGRESS', meta=metadata)


def jsonify_metadata(metadatas):
    out = []
    for metadata in metadatas:
        out.append({attr: field for attr, field in metadata.filled_fields()})
    return out


def merge_metadatas(metadatas):
    if len(metadatas) == 0:
        return audiotools.MetaData()
    elif len(metadatas) == 1:
        return metadatas[0]
    else:
        merged = metadatas[0]
        for to_merge in metadatas[1:]:
            merged = merged.intersection(to_merge)
        return merged


@celery.task(bind=True)
def rip_disk(self):
    """Most of this is just copied from cdda2track, a part of python-audio-tools"""
    try:
        cddareader = CDDAReader(app.config['ripper']['cdrom'], True)
        track_offsets = cddareader.track_offsets
        track_lengths = cddareader.track_lengths
    except (IOError, ValueError, OSError) as err:
        self.update_state(state='FAILURE', meta={'error': str(err)})
        raise Ignore()

    if "offset" in app.config['ripper']:
        read_offset = app.config['ripper']['offset']
    else:
        read_offset = 0
    if "speed" in app.config['ripper']:
        cddareader.set_speed(app.config['ripper']['speed'])

    pre_gap_length = cddareader.track_offsets[1]
    if pre_gap_length > 0:
        with audiotools.BufferedPCMReader(audiotools.PCMReaderWindow(cddareader,
                                                                     read_offset,
                                                                     pre_gap_length,
                                                                     forward_close=False)) as r:
            preserve_pre_gap = set(r.read(pre_gap_length)) != {0}
            if preserve_pre_gap:
                track_offsets[0] = 0
                track_lengths[0] = pre_gap_length
    else:
        preserve_pre_gap = False

    self.update_state(state='PROGRESS', meta={'current': None,
                                              'total': None,
                                              'album': None,
                                              'artist': None,
                                              'metadata': [],
                                              'status': 'Reading metadata'})
    metadata_choices = audiotools.cddareader_metadata_lookup(cddareader)

    if preserve_pre_gap:
        # prepend "track 0" track to start of list for each choice
        for choice in metadata_choices:
            track_0 = merge_metadatas(choice)
            track_0.track_number = 0
            choice.insert(0, track_0)

    album = metadata_choices[0][0].album_name
    artist = metadata_choices[0][0].artist_name
    self.update_state(state='PROGRESS', meta={'current': None,
                                              'total': len(track_offsets),
                                              'album': album,
                                              'artist': artist,
                                              'metadata': jsonify_metadata(metadata_choices[0]),
                                              'status': 'Got metadata, preparing to rip'})

    tracks_to_rip = list(sorted(track_offsets.keys()))
    try:
        output_tracks = list(
            process_output_options(
                metadata_choices=[
                    [c for i, c in
                     enumerate(choices, 0 if preserve_pre_gap else 1)
                     if i in tracks_to_rip]
                    for choices in metadata_choices],
                input_filenames=[
                    audiotools.Filename("track{:02d}.cdda.wav".format(i))
                    for i in tracks_to_rip],
                output_directory=app.config['ripper']['output_directory'],
                format_string=None,
                output_class=audiotools.wav.WaveAudio,
                quality='',
                msg=msg,
                use_default=True))
    except audiotools.UnsupportedTracknameField as err:
        self.update_state(state='FAILURE', meta={'error': str(err)})
        raise Ignore()

    encoded = []
    rip_log = {}
    accuraterip_log_v1 = {}
    accuraterip_log_v2 = {}
    replay_gain = audiotools.ReplayGainCalculator(cddareader.sample_rate)

    for (track_number,
         index,
         (output_class,
          output_filename,
          output_quality,
          output_metadata)) in zip(tracks_to_rip,
                                   range(1, len(tracks_to_rip) + 1),
                                   output_tracks):
        self.update_state(state='PROGRESS', meta={'current': track_number,
                                                  'total': len(tracks_to_rip),
                                                  'album': album,
                                                  'artist': artist,
                                                  'metadata': jsonify_metadata(metadata_choices[0]),
                                                  'status': 'Preparing to rip'})
        cddareader.reset_log()
        track_offset = (track_offsets[track_number] +
                        read_offset -
                        PREVIOUS_TRACK_FRAMES)
        track_length = track_lengths[track_number]

        # seek to indicated starting offset
        if track_offset > 0:
            seeked_offset = cddareader.seek(track_offset)
        else:
            seeked_offset = cddareader.seek(0)

        # make leading directories, if necessary
        try:
            audiotools.make_dirs(str(output_filename))
        except OSError as err:
            self.update_state(state='FAILURE', meta={'error': str(err)})
            raise Ignore()

        # setup individual progress bar per track
        state = {'current': track_number,
                 'total': len(tracks_to_rip),
                 'album': album,
                 'artist': artist,
                 'metadata': jsonify_metadata(metadata_choices[0]),
                 'status': 'Ripping...'}
        progress = CeleryProgressDisplay(msg, state, self)

        # perform extraction over an AccurateRip window
        track_data = audiotools.PCMReaderWindow(
            cddareader,
            track_offset - seeked_offset,
            PREVIOUS_TRACK_FRAMES + track_length + NEXT_TRACK_FRAMES)

        # with AccurateRip calculated during extraction
        accuraterip = AccurateRipReader(
            track_data,
            track_length,
            track_number == min(track_offsets.keys()),
            track_number == max(track_offsets.keys()))

        try:
            # encode output file itself
            track = output_class.from_pcm(
                str(output_filename),
                replay_gain.to_pcm(
                    audiotools.PCMReaderProgress(
                        audiotools.PCMReaderWindow(
                            accuraterip,
                            PREVIOUS_TRACK_FRAMES,
                            track_length,
                            forward_close=False),
                        track_length,
                        progress.update)),
                output_quality,
                total_pcm_frames=track_length)
            encoded.append(track)

            # since the inner PCMReaderWindow only outputs part
            # of the accuraterip reader, we need to ensure
            # anything left over in accuraterip gets processed also
            audiotools.transfer_data(accuraterip.read, lambda f: None)
        except audiotools.EncodingError as err:
            self.update_state(state='FAILURE', meta={'error': str(err)})
            raise Ignore()

        track.set_metadata(output_metadata)

        rip_log[track_number] = cddareader.log()
        accuraterip_log_v1[track_number] = accuraterip.checksums_v1()
        accuraterip_log_v2[track_number] = accuraterip.checksums_v2()

    self.update_state(state='SUCCESS', meta={'total': len(tracks_to_rip),
                                             'album': album,
                                             'artist': artist,
                                             'metadata': jsonify_metadata(metadata_choices[0]),
                                             'status': 'Fully ripped'})

    return {'status': 'done', 'tracks': len(tracks_to_rip)}


@celery.task
def mtx_command(command, **kwargs):
    if command == "update_status":
        changer.update_status()
    if command == "load":
        slot = None
        if "slot" in kwargs:
            slot = kwargs['slot']
        changer.load(slot)
    if command == "unload":
        changer.unload(kwargs['slot'])
    if command == "load_drive":
        drive = 0
        if "drive" in kwargs:
            drive = kwargs["drive"]
        changer.load_drive(kwargs['slot'], drive)
    return changer.get_status()
