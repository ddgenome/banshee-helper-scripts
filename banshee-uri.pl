#! /usr/bin/env perl
# correct uri of tracks when they get out of sync
# one time hack, do not use without checking
# currently set up to move music from Music to Music/Banshee
use warnings;
use strict;

use DBI;
use Getopt::Long;

my $pkg = 'banshee-uri';
my $version = '0.2';

my ($check);
unless (GetOptions(help => sub { print "$pkg [OPTIONS]...\n" },
                   check => \$check,
                   version => sub { print "$pkg $version\n" }
                  ))
{
    warn("Try `$pkg --help' for more information.\n");
    exit(1);
}

# connect to database
my $bdb = "$ENV{HOME}/.config/banshee-1/banshee.db";
my $dbh = DBI->connect(
    "dbi:SQLite:dbname=$bdb", '', '', { RaiseError => 1, AutoCommit => 0 }
);
if (!defined($dbh)) {
    warn("$pkg: failed to open Banshee database");
    exit(1);
}

# prepare select query
my $uri_prefix = "file://$ENV{HOME}/Music";
my $track_q = qq(
  select t.TrackID, t.Uri
  from CoreTracks as t
  where Uri like '$uri_prefix%'
);
my $track_s = $dbh->prepare($track_q);

# prepare update query
my $update_q = q(
  update CoreTracks
  set Uri = ?
  where TrackID = ?
);
my $update_s = $dbh->prepare($update_q);

# get tracks and start loop
$track_s->execute;
my ($tracks, $updates) = (0, 0);
while (my $row = $track_s->fetchrow_arrayref) {
    ++$tracks;
    my ($id, $old_uri) = @$row;

    # fix uri
    my $uri = $old_uri;
    if ($uri =~ s/^$uri_prefix/$uri_prefix\/Banshee/) {
        ++$updates;
    }
    else {
        # strange given select conditional
        warn("$pkg: unable to update uri: $uri\n");
        next; # while $row
    }

    # update track
    if ($check) {
        print("$pkg: $id:$old_uri => $uri\n");
        # no need to check every last track
        last if $updates > 20; # while $row
    }
    else {
        $update_s->execute($uri, $id);
    }
}
print("$pkg: processed $tracks tracks, updated $updates tracks\n");

$track_s->finish;
$update_s->finish;
$dbh->commit;
$dbh->disconnect;

exit(0);
