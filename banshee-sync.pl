#! /usr/bin/env perl
# get ratings and playcounts from old banshee database
use warnings;
use strict;

use DBI;
use Getopt::Long;

my $pkg = 'banshee-sync';
my $version = '0.1';

my ($check);
unless (GetOptions(help => sub { print "$pkg [OPTIONS]...\n" },
                   check => \$check,
                   version => sub { print "$pkg $version\n" }
                  ))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to databases
my $db_home = 'test';
#my $db_home = '$ENV{HOME}/.config/banshee-1';
my $old_dbh = DBI->connect(
    "dbi:SQLite:dbname=$db_home/banshee.db.old",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);
my $new_dbh = DBI->connect(
    "dbi:SQLite:dbname=$db_home/banshee.db",
    '', '', { RaiseError => 1, AutoCommit => 0 }
);

my $track_q = q(
  select t.TrackID, t.TitleLowered, t.TrackNumber, t.Year, t.Genre, t.Rating,
    t.PlayCount, t.LastPlayedStamp, t.DateAddedStamp, t.DateUpdatedStamp,
    a.NameLowered, l.TitleLowered
  from CoreTracks as t
    join CoreArtists as a on t.ArtistID = a.ArtistID
    join CoreAlbums as l on t.AlbumID = l.AlbumID
  where t.Genre <> 'Podcast'
);
my @track_k = qw(TrackID TitleLowered TrackNumber Year Genre Rating
    PlayCount LastPlayedStamp DateAddedStamp DateUpdatedStamp
    ArtistNameLowered AlbumTitleLowered);
my $track_s = $new_dbh->prepare($track_q);
my $match_q = q(
  select t.TrackNumber, t.Year, t.Genre, t.Rating,
    t.PlayCount, t.LastPlayedStamp, t.DateAddedStamp, t.DateUpdatedStamp
  from CoreTracks as t
    join CoreArtists as a on t.ArtistID = a.ArtistID
    join CoreAlbums as l on t.AlbumID = l.AlbumID
  where t.TitleLowered = ?
    and l.TitleLowered = ?
    and a.NameLowered = ?
);
my @match_k = qw(TrackNumber Year Genre Rating
    PlayCount LastPlayedStamp DateAddedStamp DateUpdatedStamp);
my @match_w = qw(TitleLowered AlbumTitleLowered ArtistNameLowered);
my $match_s = $old_dbh->prepare($match_q);

my $update_q = q(
  update CoreTracks
  set TrackNumber = ?, Year = ?, Genre = ?, Rating = ?, PlayCount = ?,
    LastPlayedStamp = ?, DateAddedStamp = ?, DateUpdatedStamp = ?
  where TrackID = ?
);
my @update_k = qw(TrackNumber Year Genre Rating PlayCount LastPlayedStamp
    DateAddedStamp DateUpdatedStamp);
my $update_s = $new_dbh->prepare($update_q);

# get tracks and start loop
$track_s->execute;
my ($tracks, $updated) = (0, 0);
while (my $row = $track_s->fetchrow_arrayref) {
    ++$tracks;
    my %track;
    @track{@track_k} = @$row;
    my $track_str = join(',', @track{'TrackID', @match_w});

    # get matching track
    $match_s->execute(@track{@match_w});
    my $match_rows = $match_s->fetchall_arrayref;
    if (@$match_rows == 1) {
        print("$pkg: updating $track_str\n");

        # synchronize records (assumes match is the older record)
        my (%match, %update);
        @match{@match_k} = @{$match_rows->[0]};
        # default to no op
        @update{@update_k} = @track{@update_k};

        # loop through attributes
        foreach my $attr (@update_k) {
            # use old value if new value not set
            if ($match{$attr} && !$track{$attr}) {
                $update{$attr} = $match{$attr};
            }
        }
        # use earlier add date
        $update{DateAddedStamp} = $match{DateAddedStamp};
        # add up play counts
        if (defined($match{PlayCount}) && defined($track{PlayCount})) {
            $update{PlayCount} = $match{PlayCount} + $track{PlayCount};
        }

        # update record
        if ($check) {
            my $track_str = join(',', @track{'TrackID', @match_w});
            print("$pkg:   h:", join(',', @update_k), "\n");
            print("$pkg:   t:", hash2string(\%track, @update_k), "\n");
            print("$pkg:   m:", hash2string(\%match, @update_k), "\n");
            print("$pkg:   u:", hash2string(\%update, @update_k), "\n");
            #last if $updated > 100; # while $row
        }
        else {
            $update_s->execute(@update{@update_k}, $track{TrackID});
        }
        ++$updated;
    }
    elsif (@$match_rows > 1) {
        warn("$pkg: track matched more than one track: $track_str\n");
        next;
    }
    else {
        warn("$pkg: track has no match: $track_str\n");
    }
}
print("$pkg: Processed $tracks tracks, Updated $updated row(s)\n");

$track_s->finish;
$match_s->finish;
$update_s->finish;
$old_dbh->disconnect;
#$new_dbh->rollback;
$new_dbh->commit;
$new_dbh->disconnect;

exit(0);

sub row2string {
    my ($row) = @_;
    return join(',', map { defined($_) ? $_ : '{NULL}' } @$row);
}

sub hash2string {
    my ($hash, @keys) = @_;
    return join(',', map { defined($_) ? $_ : '{NULL}' } @$hash{@keys});
}

__END__

sqlite> select * from CoreTracks where TrackID = 6608;
1|6608|338|613|0|0||file:///gscuser/ddooling/archive/music/ogg/whiskeytown/strangers_almanac/02_excuse_me_while_i_break_my_own_heart_tonight.ogg|2|taglib/ogg|3039317|128|5|0|Excuse Me While I Break My Own Heart Tonight|excuse me while i break my own heart tonight|2|0|0|0|194893|0|rock|||||||0|0|0|||1236969661|1236969661|cc303298e1db0839e0e83c5c631c729e|0|1236969661|1018631800
sqlite> select * from CoreTracks where TrackID = 6608;
1|6608|338|613|0|0||file:///gscuser/ddooling/archive/music/ogg/whiskeytown/strangers_almanac/02_excuse_me_while_i_break_my_own_heart_tonight.ogg|2|taglib/ogg|3039317|128|5|0|Excuse Me While I Break My Own Heart Tonight|excuse me while i break my own heart tonight|2|0|0|0|194893|0|rock|||||||0|1|0|1237836090||1236969661|1237836090|cc303298e1db0839e0e83c5c631c729e|0|1236969661|1018631800
# need to update PlayCount, LastPlayedStamp, DateUpdatedStamp
sqlite> update CoreTracks set PlayCount = 1, LastPlayedStamp = 1237913799, DateUpdatedStamp = 1237913799 where Uri like '%velvet_underground__nico%';
