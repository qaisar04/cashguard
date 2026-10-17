package kz.cashguard.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class ApiKeyFilterTest {

    private static final String KEY = "secret";
    private final ApiKeyFilter filter = new ApiKeyFilter(KEY, new ObjectMapper());

    @Test
    void rejectsMissingKeyOnApiPath() throws Exception {
        var request = new MockHttpServletRequest("GET", "/api/v1/jobs/1");
        var response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(response.getContentAsString()).contains(ApiKeyFilter.HEADER);
        verifyNoInteractions(chain);
    }

    @Test
    void rejectsWrongKey() throws Exception {
        var request = new MockHttpServletRequest("GET", "/api/v1/jobs/1");
        request.addHeader(ApiKeyFilter.HEADER, "nope");
        var response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(401);
        verifyNoInteractions(chain);
    }

    @Test
    void passesCorrectKey() throws Exception {
        var request = new MockHttpServletRequest("GET", "/api/v1/jobs/1");
        request.addHeader(ApiKeyFilter.HEADER, KEY);
        var response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
    }

    @Test
    void ignoresNonApiPaths() throws Exception {
        var request = new MockHttpServletRequest("GET", "/index.html");
        var response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
    }
}
