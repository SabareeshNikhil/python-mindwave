import mindwave
import sys
import subprocess
import re
import matplotlib
import matplotlib.pyplot as plt
from time import sleep
import spotipy
import numpy as np
import spotipy.util as util
import spotipy.client as client
from pprint import pprint
import yaml
import random
from spotipy.oauth2 import SpotifyClientCredentials


#matplotlib.use("TkAgg")
port = '/dev/tty.MindWaveMobile-DevA-'

def load_config():
    global user_config
    stream = open('config.yaml')
    user_config = yaml.load(stream)
    #pprint(user_config)

def aggregate_top_artists(sp):
    print('...getting your top artists')
    top_artists_name = []
    top_artists_uri = []

    ranges = ['short_term', 'medium_term', 'long_term']
    for r in ranges:
        top_artists_all_data = sp.current_user_top_artists(limit=50, time_range= r)
        top_artists_data = top_artists_all_data['items']
        for artist_data in top_artists_data:
            if artist_data["name"] not in top_artists_name:
                top_artists_name.append(artist_data['name'])
                top_artists_uri.append(artist_data['uri'])

    followed_artists_all_data = sp.current_user_followed_artists(limit=50)
    followed_artists_data = (followed_artists_all_data['artists'])
    for artist_data in followed_artists_data["items"]:
        if artist_data["name"] not in top_artists_name:
            top_artists_name.append(artist_data['name'])
            top_artists_uri.append(artist_data['uri'])
    return top_artists_uri


#Step 3. For each of the artists, get a set of tracks for each artist

def aggregate_top_tracks(sp, top_artists_uri):
    print("...getting top tracks")
    top_tracks_uri = []
    for artist in top_artists_uri:
        top_tracks_all_data = sp.artist_top_tracks(artist)
        top_tracks_data = top_tracks_all_data['tracks']
        for track_data in top_tracks_data:
            top_tracks_uri.append(track_data['uri'])
    return top_tracks_uri

# Step 4. From top tracks, select tracks that are within a certain mood range

def select_tracks(sp, mood, top_tracks_uri):
    
    print("...selecting tracks")
    selected_tracks_uri = []

    def group(seq, size):
        return (seq[pos:pos + size] for pos in range(0, len(seq), size))

    random.shuffle(top_tracks_uri)
    for tracks in list(group(top_tracks_uri, 50)):
        tracks_all_data = sp.audio_features(tracks)
        for track_data in tracks_all_data:
            try:
                if mood < 0.10:
                    if (0 <= track_data["valence"] <= (mood + 0.15)
                    and track_data["danceability"] <= (mood*8)
                    and track_data["energy"] <= (mood*10)):
                        selected_tracks_uri.append(track_data["uri"])
                elif 0.10 <= mood < 0.25:
                    if ((mood - 0.075) <= track_data["valence"] <= (mood + 0.075)
                    and track_data["danceability"] <= (mood*4)
                    and track_data["energy"] <= (mood*5)):
                        selected_tracks_uri.append(track_data["uri"])
                elif 0.25 <= mood < 0.50:
                    if ((mood - 0.05) <= track_data["valence"] <= (mood + 0.05)
                    and track_data["danceability"] <= (mood*1.75)
                    and track_data["energy"] <= (mood*1.75)):
                        selected_tracks_uri.append(track_data["uri"])
                elif 0.50 <= mood < 0.75:
                    if ((mood - 0.075) <= track_data["valence"] <= (mood + 0.075)
                    and track_data["danceability"] >= (mood/2.5)
                    and track_data["energy"] >= (mood/2)):
                        selected_tracks_uri.append(track_data["uri"])
                elif 0.75 <= mood < 0.90:
                    if ((mood - 0.075) <= track_data["valence"] <= (mood + 0.075)
                    and track_data["danceability"] >= (mood/2)
                    and track_data["energy"] >= (mood/1.75)):
                        selected_tracks_uri.append(track_data["uri"])
                elif mood >= 0.90:
                    if ((mood - 0.15) <= track_data["valence"] <= 1
                    and track_data["danceability"] >= (mood/1.75)
                    and track_data["energy"] >= (mood/1.5)):
                        selected_tracks_uri.append(track_data["uri"])
            except TypeError as te:
                continue

    return selected_tracks_uri

# Step 5. From these tracks, create a playlist for user

def create_playlist(sp, selected_tracks_uri):

    print("...creating playlist")
    user_all_data = sp.current_user()
    user_id = user_all_data["id"]

    playlist_all_data = sp.user_playlist_create(user_id, "EEG - " + str(np.round(mood, 4)))
    playlist_id = playlist_all_data["id"]

    random.shuffle(selected_tracks_uri)
    sp.user_playlist_add_tracks(user_id, playlist_id, selected_tracks_uri[0:30])

    return playlist_id


def delete_playlist(sp, pid):
    
    print("...deleting old playlist")
    user_all_data = sp.current_user()
    user_id = user_all_data["id"]
    
    sp.user_playlist_unfollow(user_id, pid)
    return pid


def select_playlist(sp, flag) :
    pl = 'playlist_id_' + flag
    sp.start_playback(user_config['device_id'], user_config[pl])
    return flag


def process_mood (sp, headset) :
    med_array = []
    att_array = []
    i = 0
    while len(med_array) < 100 :
        sleep(0.1)
        if headset.meditation or headset.attention :
            print(headset.meditation, headset.attention)
            med_array.append(headset.meditation)
            att_array.append(headset.attention)
    med = np.mean(med_array)
    att = np.mean(att_array)
    mood = (att - med)/200.0 + 0.50
    return mood


if __name__ == '__main__':
    global sp
    global user_config
    global med
    global att
    global mood
    global headset
    headset = mindwave.Headset(port + sys.argv[1], '625f')
    headset.autoconnect()
    headset.connect()
    med = 0
    att = 0
    mood = 0.5
    mood_old = 0
    load_config()
    token = util.prompt_for_user_token(user_config['username'], scope='user-follow-read,user-top-read,user-modify-playback-state,user-read-playback-state,streaming,app-remote-control,playlist-modify-private,playlist-modify-public', client_id=user_config['client_id'], client_secret=user_config['client_secret'], redirect_uri=user_config['redirect_uri'])
    spotify_auth = spotipy.Spotify(auth=token)
    top_artists = aggregate_top_artists(spotify_auth)
    top_tracks = aggregate_top_tracks(spotify_auth, top_artists)
    while token:
        if np.abs(mood - mood_old) > 0.05 :
            selected_tracks = select_tracks(spotify_auth, mood, top_tracks)
            try :
                pid_old = pid
            except :
                pass
            pid = create_playlist(spotify_auth, selected_tracks)
            spotify_auth.start_playback(device_id=user_config['device_id'], context_uri='spotify:playlist:' + pid)
            try :
                delete_playlist(spotify_auth, pid_old)
            except :
                pass
        mood_old = mood
        mood = process_mood(spotify_auth, headset)
    else:
        print ("Can't get token for", user_config['username'])
    headset.disconnect()

    #bt = subprocess.Popen('system_profiler SPBluetoothDataType | grep MindWaveMobile | tail -1').read().decode()
    #(med_array, att_array) = connect(port + sys.argv[1])
    #plt.scatter(range(len(med_array)), med_array, color='b')
    #plt.hold()
    #plt.scatter(range(len(att_array)), att_array, color='r')
plt.show()
