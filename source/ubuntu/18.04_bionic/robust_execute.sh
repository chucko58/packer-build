#! /bin/bash
# This file is meant to be included by another shell script.

##########################################
#
# robust_execute
#
# Executes the command and captures any output to stderr.
# On failure, if the error message matches robust_execute_re,
# repeats the command up to robust_execute_retries times.
# Otherwise echoes the error message to stderr and
# returns with nonzero status.
#
##########################################

# # of times we should try to execute
robust_execute_retries=3

# Regexp for error msgs which allow retry
robust_execute_re=

robust_execute()
{
    # Place to temporarily store stderr output
    tmp_stderr="$(mktemp)"

    for (( retries_left=robust_execute_retries ; retries_left ; --retries_left ))
    do
        if "$@" 2> "$tmp_stderr"
        then
            # Success
            cat < "$tmp_stderr" >&2
            rm -f "$tmp_stderr"
            return 0
        fi

        # Failed, is it an error we care about?
        if [ -n "$robust_execute_re" ] && grep -e "$robust_execute_re" < "$tmp_stderr" > /dev/null
        then
            echo '*** Caught error:'
            cat < "$tmp_stderr" >&2
            echo '*** Retrying...'
        else
            break
        fi
    done

    # Ran out of retries, or not an error we can retry from
    cat < "$tmp_stderr" >&2
    rm -f "$tmp_stderr"
    echo "robust_execute: ${@} failed"
    return 1
}

# Test
# bogus()
# {
#     echo 'Foo!' > /dev/stderr
#     return 1
# }

# robust_execute_re='Foo!$'

# robust_execute /bin/echo 'Foo!'

# robust_execute bogus
