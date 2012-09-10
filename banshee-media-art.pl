#! /usr/bin/env perl
# output path to media art for given album/artist
# see https://bugzilla.gnome.org/show_bug.cgi?id=520516#c58
use warnings;
use strict;

use Digest::MD5 qw(md5_hex);
use Getopt::Long;
use Pod::Usage;
use Unicode::Normalize;

my $pkg = 'banshee-media-art';
my $version = '0.1';

my ($ignore_case, $verbose);
my %new = (ext => '.flac', mime => 'tablib/flac');
if (!&GetOptions(help => sub { &pod2usage(-exitval => 0) },
                 verbose => \$verbose,
                 version => sub { print "$pkg $version\n"; exit(0) }))
{
    warn("Try ``$pkg --help'' for more information.\n");
    exit(1);
}

# get artist and album
if (@ARGV < 2) {
    warn("$pkg: improper number of arguments: @ARGV\n");
    warn("Try ``$pkg --help'' for more information.\n");
    exit(1);
}
my ($artist, $album) = @ARGV;

# convert to NFKD
my $nfkd = NFKD("$artist\t$album");
print("$pkg: NFKD: $nfkd\n") if $verbose;
# create md5
my $md5 = md5_hex($nfkd);
print("$pkg: MD5: $md5\n") if $verbose;
# set path
my $base = "$ENV{HOME}/.cache/media-art/album-$md5";
my $path;
foreach my $ext (qw(jpg cover)) {
    my $file = "$base.$ext";
    if (-f $file) {
        # found file, break loop
        $path = $file;
        last; # foreach $ext
    }
}
# see if we found the file
if (!$path) {
    warn("$pkg: no file with know extension found: $base");
    # look for any extension
    my @files = glob("$base.*");
    if (@files) {
        warn("$pkg: files that match: " . join(',', @files));
    }
    exit(1);
}
print("$path\n");

exit(0);

__END__

=pod

=head1 NAME

banshee-2flac - update banshee database to use flac

=head1 SYNOPSIS

B<banshee-media-art> [OPTIONS]... ARTIST ALBUM

=head1 DESCRIPTION

This script updates the banshee music database to use a FLAC file, if it
exists, rather than a compressed audio file format.  The script will
update an entire album if given the ARTIST name and ALBUM title.  If the
optional track number is also give, it will update just that track (this
is useful if an album was previously updated but some tracks failed due
to file name mismatching).

=head1 OPTIONS

If an argument to a long option is mandatory, it is also mandatory for
the corresponding short option; the same is true for optional arguments.

=over 4

=item -h, --help

Display a brief description and listing of all available options.

=item -v, --version

Output version information and exit.

=item --

Terminate option processing.  This option is useful when file names
begin with a dash (-).

=back

=head1 BUGS

No known bugs.

=head1 SEE ALSO

L<banshee(1)>, L<https://bugzilla.gnome.org/show_bug.cgi?id=520516#c58>,
L<https://live.gnome.org/MediaArtStorageSpec>

=head1 AUTHOR

David Dooling <dooling@gmail.com>

=cut
